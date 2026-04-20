## **Bitcoin Investing Tool**

This repository presents a data engineering project implementing an
end-to-end ELT pipeline combined with an analytical application designed
to support long-term Bitcoin investing.

The system integrates multiple data sources, processes them using modern
data engineering tools, and delivers insights through an interactive
Streamlit application. The project demonstrates a complete workflow
including data ingestion, transformation, orchestration, and deployment.

------------------------------------------------------------------------

## **Architecture**

![Architecture](https://i.postimg.cc/MZFm3CJg/Group-12.jpg)

------------------------------------------------------------------------

## **Overview**

The project is built around a modular ELT pipeline with clear separation
of responsibilities:

-   Data ingestion from external sources (`Binance API` and `AWS S3`)
-   Storage in a cloud-based data warehouse (`Snowflake`)
-   Transformation and testing using `dbt`
-   Orchestration with `Apache Airflow`
-   Serving layer via `Streamlit` application
-   Deployment and infrastructure using `Docker` and cloud hosting
-   CI/CD integration via `GitHub Actions`

The pipeline is designed to operate incrementally using a watermark
(last timestamp), ensuring efficient processing and avoiding full data
reloads.

------------------------------------------------------------------------
## **Application**

![Application](https://i.postimg.cc/BQxcZNVN/screenshot.jpg)

### **Key components**

- **Bitcoin price chart (weekly interval)**
  - Main analytical view focused on long-term trends
  - Weekly granularity is used to reduce noise and support strategic decision-making
  - Daily interval is available for deeper analysis when needed

- **Supertrend indicator**
  - Primary analytical tool used in the application
  - Helps identify long-term trend direction and potential reversal points
  - Has proven effective in capturing major market cycles

- **Market summary**
  - Aggregated view of market metrics
  - Provides quick situational awareness for the current market state

- **Whale inflow monitoring**
  - Tracks large-volume movements on the blockchain
  - Based on on-chain data
  - Updated hourly to detect potential accumulation or distribution phases

### **Design assumptions**

The application is optimized for long-term investing:

- Focus on higher timeframes (weekly data)
- Limited need for high-frequency ingestion (daily batches)
- Separation of data sources:
  - market data (daily)
  - blockchain data (hourly)

## **Tools used**

**Languages, frameworks and environments:**

    > Python
    > SQL
    > Docker / Docker Compose
    > Streamlit
    > GitHub Actions

**Data engineering and orchestration:**

    > Apache Airflow
    > dbt
    > Snowflake

**Libraries and packages:**

    > pandas
    > numpy
    > plotly
    > snowflake-connector-python

**Monitoring:**

    > Prometheus
    > Grafana
    

## **Getting started**

``` bash
git clone https://github.com/your-username/bitcoin-investing-tool
cd bitcoin-investing-tool

cp .env.example .env

docker compose up --build
```

