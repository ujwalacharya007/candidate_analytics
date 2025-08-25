
# Election Analytics Automation

A Streamlit app that accepts your Excel file and automatically generates:
1. **Vote Analysis** – totals by party across district/local level/ward, strongholds & weakholds, position patterns.
2. **Candidate Insights** – performance by age, gender, and position; top over/under-performers.
3. **Geographical Strategy (lists)** – low-vote areas for your party and opposition-dominant areas.
4. **Trend Analysis** – trends over wards by gender and age groups.
5. **Performance Optimization** – low-share areas and simple correlations.

## How to run
1. Install Python 3.10+
2. Create a virtual environment (optional but recommended)
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the app:
   ```bash
   streamlit run app.py
   ```
5. In the app, upload your Excel. Nepali headers are auto-detected and normalized.

## Notes
- The app expects columns equivalent to **party** and **votes** at minimum.
- Optional columns increase insights: **district, local_level, ward, position, gender, age**.
- No shapefiles/GeoJSON are required. Mapping is expressed as prioritized lists and charts. A future version can add choropleth maps if you provide boundaries.
