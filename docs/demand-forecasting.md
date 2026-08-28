# Demand forecasting and anomaly detection

The forecast endpoint turns persisted daily warehouse metrics into explainable short-term
forecasts. It supports reservations, booked minutes, cancellations, no-shows, and net
revenue in an explicitly selected currency.

```http
GET /analytics/venues/7/forecast?metric=reservations&as_of_date=2026-08-27&horizon_days=7&history_days=84
```

For revenue, include a currency so unlike amounts are never combined:

```http
GET /analytics/venues/7/forecast?metric=net_revenue&currency=EUR&as_of_date=2026-08-27
```

## Model

`weekday-seasonal-trend-v1` averages up to eight observations for the target weekday,
then applies a bounded ratio between the latest and previous 14-day windows. This is a
transparent baseline suited to the relatively short history of a booking application.
It needs no external ML runtime and provides a standard that a future model must beat.

Days absent from the aggregate table are materialized as zero activity. Forecast ranges
use 1.96 times the walk-forward mean absolute error and never fall below zero.

## Evaluation and anomalies

Accuracy uses expanding-window, one-step-ahead backtesting. Every prediction sees only
the observations that preceded it, avoiding target leakage. The response reports MAE
and MAPE; zero actual values are excluded from MAPE because percentage error is undefined.

For the latest seven observations, residuals are standardized against older backtest
residuals. Values at least two standard deviations from expected are returned as upward
or downward anomalies. These are operational signals, not proof of a causal event.

Forecasts are limited to 30 days because uncertainty grows rapidly beyond that range.
History is configurable from 14 to 365 days. Owners retain the same venue-level access
controls as the rest of analytics.
