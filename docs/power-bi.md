# Power BI CSV integration

No PBIX file is supplied or claimed to have been verified. DeliveryGuard exports
standard UTF-8 BOM CSVs readable by Power BI Desktop and other BI tools.

1. In **Analyse des livraisons**, download `orders.csv`; in **Commandes à surveiller**,
   download `risk_scores.csv` after a prediction. Or fetch `/exports/orders.csv` via
   an authenticated integration. Avoid embedding the shared key in a published workbook.
2. In Power BI Desktop choose **Get data → Text/CSV**, select UTF-8 and comma.
3. In Power Query keep `order_id` as **Text**, parse the three timestamps as
   **Date/Time/Timezone**, `weight_kg`, `order_amount`, `risk_score` as decimal
   numbers, and `observed_late` as nullable whole number. Use a locale with decimal
   dot for numeric conversion; do not change the CSV's underlying precision.
4. `observed_late` is 0/1 only for delivered orders. Nulls for open/cancelled must
   stay null; do not replace them with 0. Rate = sum(observed_late) / non-null count.
5. Join risk rankings by order_id if the new orders also appear in stored history.
   The ranking export includes model_id and threshold for traceability.
   A score is not a calibrated probability and overdue alerts are separate.
6. For scheduled local refresh, save authenticated exports to a company-controlled
   folder and use your organization's existing Power BI gateway. Nothing here
   provisions a gateway, publishes a dataset, or sends data to Microsoft by default.

The CSVs use ISO 8601 timestamps, stable IDs and numeric values, not formatted
percentage strings. Human-facing exports escape formula-like leading characters;
the source CSV is preserved separately. Review those escaped category/ID cells
before a BI join if your source codes deliberately begin with `=`, `+`, `-` or `@`.
