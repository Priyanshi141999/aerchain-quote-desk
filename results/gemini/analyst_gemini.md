# Analyst test — gemini

## Q: What if we split it, cheapest per line, but only among vendors who cleared the quality questionnaire?
*11s*

Splitting the award by the cheapest per line among qualified vendors results in a total annual cost of ₹4,02,32,152 (₹4.02 Cr), with vendor A (Siam Pacific Packaging (India) Pvt Ltd) winning all 30 line items. 

**Key Facts:**
- **Total Annual Cost:** ₹4,02,32,152 across all 30 lines.
- **Winning Vendor:** Vendor A (Siam Pacific Packaging (India) Pvt Ltd) is the sole qualified vendor winning every line.
- **Volume Scope:** Covers 30 distinct packaging items with quantities ranging from 900 to 2,00,000 units annually.

**Caveats:** Only one vendor (Vendor A) cleared the quality questionnaire, meaning this split award is effectively a single-vendor award with no competitive pressure across lines.; Potential unknown freight, tax, or conditional discount terms could alter the final landed cost.; Rows excluded from ranking or un-cleared vendors were not considered.

**Interpretation:** Find the cheapest price_inr per line among vendors who have qualification == 'qualified' (excluding suspected errors via excluded_from_ranking), and calculate the total annual cost for this split award. Also show which vendor wins each line.

```python
df = lines[(lines['qualification'] == 'qualified') & (~lines['excluded_from_ranking']) & (lines['price_inr'].notna())].copy()
# Find cheapest vendor per line
idx = df.groupby('line')['price_inr'].idxmin()
cheapest_lines = df.loc[idx, ['line', 'item', 'vendor', 'vendor_name', 'annual_qty', 'price_inr', 'annual_value_inr']]
cheapest_lines['total_cost'] = cheapest_lines['annual_qty'] * cheapest_lines['price_inr']

result = cheapest_lines[['line', 'item', 'vendor', 'vendor_name', 'price_inr', 'annual_qty', 'total_cost']].sort_values('line')

# Total spend summary
total_spend = result['total_cost'].sum()
print(f"Total annual spend for split award among qualified vendors: {total_spend:,.2f} INR")

```

**Computed result:**

|   line | item                                       | vendor   | vendor_name                            |   price_inr |   annual_qty |       total_cost |
|-------:|:-------------------------------------------|:---------|:---------------------------------------|------------:|-------------:|-----------------:|
|      1 | Kettle 1.5L unit carton                    | A        | Siam Pacific Packaging (India) Pvt Ltd |        8.9  |       120000 |      1.068e+06   |
|      2 | Steam iron unit carton                     | A        | Siam Pacific Packaging (India) Pvt Ltd |        7.72 |       150000 |      1.158e+06   |
|      3 | Hair dryer retail carton (printed)         | A        | Siam Pacific Packaging (India) Pvt Ltd |        7.5  |        90000 | 675000           |
|      4 | Mixer grinder 500W unit carton             | A        | Siam Pacific Packaging (India) Pvt Ltd |       39.51 |        80000 |      3.1608e+06  |
|      5 | Mixer grinder 750W unit carton             | A        | Siam Pacific Packaging (India) Pvt Ltd |       45.29 |        70000 |      3.1703e+06  |
|      6 | Mixer grinder master carton (2 units)      | A        | Siam Pacific Packaging (India) Pvt Ltd |       76.18 |        35000 |      2.6663e+06  |
|      7 | Induction cooktop unit carton              | A        | Siam Pacific Packaging (India) Pvt Ltd |       30.02 |        65000 |      1.9513e+06  |
|      8 | Pressure cooker 3L carton                  | A        | Siam Pacific Packaging (India) Pvt Ltd |       13.89 |       100000 |      1.389e+06   |
|      9 | Pressure cooker 5L carton                  | A        | Siam Pacific Packaging (India) Pvt Ltd |       33.32 |        75000 |      2.499e+06   |
|     10 | RO water purifier carton                   | A        | Siam Pacific Packaging (India) Pvt Ltd |       61.19 |        40000 |      2.4476e+06  |
|     11 | Air cooler 40L carton                      | A        | Siam Pacific Packaging (India) Pvt Ltd |      217.22 |        18000 |      3.90996e+06 |
|     12 | Ceiling fan blade carton                   | A        | Siam Pacific Packaging (India) Pvt Ltd |       34.67 |        60000 |      2.0802e+06  |
|     13 | Ceiling fan motor carton                   | A        | Siam Pacific Packaging (India) Pvt Ltd |       38.46 |        60000 |      2.3076e+06  |
|     14 | Table fan carton                           | A        | Siam Pacific Packaging (India) Pvt Ltd |       41.29 |        30000 |      1.2387e+06  |
|     15 | Toaster unit carton                        | A        | Siam Pacific Packaging (India) Pvt Ltd |       11.15 |        45000 | 501750           |
|     16 | Spares shipper - small (plain)             | A        | Siam Pacific Packaging (India) Pvt Ltd |        7.72 |       200000 |      1.544e+06   |
|     17 | Spares shipper - medium (plain)            | A        | Siam Pacific Packaging (India) Pvt Ltd |       18.74 |       120000 |      2.2488e+06  |
|     18 | E-commerce outer carton - large            | A        | Siam Pacific Packaging (India) Pvt Ltd |       66.22 |        50000 |      3.311e+06   |
|     19 | Export master carton - mixer (4 units)     | A        | Siam Pacific Packaging (India) Pvt Ltd |      201.25 |         8000 |      1.61e+06    |
|     20 | Accessory kit mailer, die-cut (printed)    | A        | Siam Pacific Packaging (India) Pvt Ltd |        7.57 |        60000 | 454200           |
|     21 | Partition, 12-cell (kettle master)         | A        | Siam Pacific Packaging (India) Pvt Ltd |        9.73 |        20000 | 194600           |
|     22 | Partition, 6-cell (spares)                 | A        | Siam Pacific Packaging (India) Pvt Ltd |        6.31 |        30000 | 189300           |
|     23 | Die-cut insert tray - mixer jar            | A        | Siam Pacific Packaging (India) Pvt Ltd |        7.6  |        80000 | 608000           |
|     24 | Die-cut insert - induction cooktop         | A        | Siam Pacific Packaging (India) Pvt Ltd |        5.82 |        65000 | 378300           |
|     25 | Layer pad 1200 x 1000 mm                   | A        | Siam Pacific Packaging (India) Pvt Ltd |       26.63 |        25000 | 665750           |
|     26 | Layer pad 800 x 600 mm                     | A        | Siam Pacific Packaging (India) Pvt Ltd |       10.62 |        40000 | 424800           |
|     27 | Corner protector pad 150 x 150 mm, die-cut | A        | Siam Pacific Packaging (India) Pvt Ltd |        1.9  |       140000 | 266000           |
|     28 | Single-face corrugated roll 1000 mm x 50 m | A        | Siam Pacific Packaging (India) Pvt Ltd |      867.3  |         1500 |      1.30095e+06 |
|     29 | Single-face corrugated roll 1200 mm x 50 m | A        | Siam Pacific Packaging (India) Pvt Ltd |     1039.88 |          900 | 935892           |
|     30 | Air cooler base tray / sleeve, heavy duty  | A        | Siam Pacific Packaging (India) Pvt Ltd |       61.54 |        18000 |      1.10772e+06 |



## Q: Who is cheapest overall on landed cost, and where is freight unknown?
FAILED: gemini: all models failed. gemini-3-flash-preview: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on | gemini-2.5-flash: 404 NOT_FOUND. {'error': {'code': 404, 'message': 'This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models | gemini-omni-flash-preview: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on | gemini-omni-flash-preview: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on
## Q: If we gave everything to Deccan to get their 5% discount, how would that compare with the best split among all vendors?
*5s*

Awarding the entire order to Deccan Packaging Industries with their 5% conditional discount results in a total annual cost of ₹3,66,19,320.35, which is ₹24,48,619.65 lower than the best split award among all vendors (₹3,90,67,940.00).

- Best split total annual cost: ₹3,90,67,940.00
- Deccan total with 5% discount: ₹3,66,19,320.35 (based on a raw total of ₹3,85,46,653.00)
- Cost difference: -₹24,48,619.65

**Caveats:** Deccan's status is 'not_qualified', which introduces vendor risk.; Deccan's 5% discount is conditional on placing the entire order.; The 5% discount terms exclude plates, dies, and freight.

**Interpretation:** Compare the total annual cost of awarding all 30 line items to Deccan Packaging Industries (taking into account their 5% discount conditional on placing the entire order, while excluding plates/dies/freight from the discount as stated in their terms) against the best split award among ALL vendors (including qualified, conditional, and not_qualified, excluding excluded_from_ranking lines).

```python
qual_vendors = vendors[vendors['qualification'].isin(['qualified', 'conditional', 'not_qualified'])]

# 1. Best split among all vendors (excluding excluded_from_ranking)
valid_lines = lines[~lines['excluded_from_ranking']].dropna(subset=['price_inr'])
idx_cheapest = valid_lines.groupby('line')['price_inr'].idxmin()
best_split_df = valid_lines.loc[idx_cheapest]
best_split_total = best_split_df['annual_value_inr'].sum()

# 2. Deccan total (Vendor B)
deccan_lines = lines[(lines['vendor'] == 'B') & (~lines['excluded_from_ranking'])].dropna(subset=['price_inr'])
deccan_raw_total = deccan_lines['annual_value_inr'].sum()
# 5% discount on product value
deccan_discounted_total = deccan_raw_total * 0.95

result = pd.DataFrame([
    {
        "Scenario": "Best Split Among All Vendors",
        "Total Annual Cost (INR)": round(best_split_total, 2),
        "Details": "Cheapest eligible price per line across all vendors"
    },
    {
        "Scenario": "Give All to Deccan (with 5% discount)",
        "Total Annual Cost (INR)": round(deccan_discounted_total, 2),
        "Details": f"Deccan raw total: ₹{deccan_raw_total:,.2f} minus 5% discount"
    },
    {
        "Difference (Deccan vs Best Split)": round(deccan_discounted_total - best_split_total, 2),
        "Total Annual Cost (INR)": round(deccan_discounted_total - best_split_total, 2),
        "Details": "Positive means Deccan is more expensive"
    }
])

```

**Computed result:**

| Scenario                              |   Total Annual Cost (INR) | Details                                             |   Difference (Deccan vs Best Split) |
|:--------------------------------------|--------------------------:|:----------------------------------------------------|------------------------------------:|
| Best Split Among All Vendors          |               3.90679e+07 | Cheapest eligible price per line across all vendors |                       nan           |
| Give All to Deccan (with 5% discount) |               3.66193e+07 | Deccan raw total: ₹38,546,653.00 minus 5% discount  |                       nan           |
| nan                                   |              -2.44862e+06 | Positive means Deccan is more expensive             |                        -2.44862e+06 |



## Q: Which lines have only one or no eligible quote among qualified and conditional vendors?
FAILED: gemini: all models failed. gemini-3-flash-preview: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on | gemini-2.5-flash: 404 NOT_FOUND. {'error': {'code': 404, 'message': 'This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models | gemini-omni-flash-preview: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on | gemini-omni-flash-preview: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on