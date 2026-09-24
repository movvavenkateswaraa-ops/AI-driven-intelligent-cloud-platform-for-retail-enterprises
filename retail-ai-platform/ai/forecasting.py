"""Sales forecasting: Ridge regression on trend + weekday + yearly seasonality features."""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from database import query_df


def _features(index: pd.DatetimeIndex, start: pd.Timestamp) -> pd.DataFrame:
    X = pd.DataFrame({"t": (index - start).days.astype(float)}, index=index)
    for d in range(7):
        X[f"dow{d}"] = (index.dayofweek == d).astype(float)
    doy = index.dayofyear.values
    X["sin"] = np.sin(2 * np.pi * doy / 365.25)
    X["cos"] = np.cos(2 * np.pi * doy / 365.25)
    return X


def daily_revenue() -> pd.Series:
    df = query_df(
        """SELECT o.order_date AS date, SUM(oi.qty * oi.unit_price) AS revenue
           FROM orders o JOIN order_items oi ON oi.order_id = o.id
           GROUP BY o.order_date ORDER BY o.order_date"""
    )
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["revenue"].asfreq("D", fill_value=0.0)


def forecast_revenue(horizon: int = 14, history_days: int = 60) -> dict:
    s = daily_revenue()
    start = s.index[0]

    # Hold-out validation on the last 28 days to report honest accuracy.
    train, test = s.iloc[:-28], s.iloc[-28:]
    m = Ridge(alpha=1.0).fit(_features(train.index, start), train.values)
    pred = m.predict(_features(test.index, start))
    mape = float(np.mean(np.abs((test.values - pred) / np.maximum(test.values, 1))) * 100)

    # Refit on all data and forecast forward.
    model = Ridge(alpha=1.0).fit(_features(s.index, start), s.values)
    resid_std = float(np.std(s.values - model.predict(_features(s.index, start))))
    future = pd.date_range(s.index[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")
    yhat = np.clip(model.predict(_features(future, start)), 0, None)

    hist = s.iloc[-history_days:]
    return {
        "history": [{"date": d.strftime("%Y-%m-%d"), "revenue": round(float(v), 2)} for d, v in hist.items()],
        "forecast": [
            {"date": d.strftime("%Y-%m-%d"), "revenue": round(float(v), 2),
             "lower": round(max(0.0, float(v) - 1.28 * resid_std), 2),
             "upper": round(float(v) + 1.28 * resid_std, 2)}
            for d, v in zip(future, yhat)
        ],
        "metrics": {"holdout_mape_pct": round(mape, 1), "model": "Ridge (trend + weekday + season)",
                    "horizon_days": horizon, "total_forecast": round(float(yhat.sum()), 2)},
    }
