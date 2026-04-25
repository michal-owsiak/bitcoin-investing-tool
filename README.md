## **Bitcoin Investing Tool**

A data engineering project with a production-ready application that supports long-term Bitcoin investing analysis.

https://bitcoin-investing-tool.com

`Snowflake` · `dbt` · `Airflow` · `Docker` · `Streamlit`

------------------------------------------------------------------------

## **Architecture**

![Architecture](./architecture.jpg)

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

![Application](./app_screenshot.jpg)

### **Key Components**

- **Bitcoin Price Chart (Weekly and Daily Timeframes)**
  - Main analytical view focused on long-term trends
  - Weekly granularity is used to reduce noise and support strategic decision-making
  - Daily interval is available for deeper analysis when needed

- **Supertrend Indicator**
  - Primary analytical tool used in the application
  - Helps identify long-term trend direction and potential reversal points
  - Has proven effective in capturing major market cycles

- **Market Summary**
  - Aggregated view of market metrics
  - Provides quick situational awareness for the current market state

- **Whale Inflow Monitoring**
  - Tracks large-volume movements on the blockchain
  - Based on on-chain data
  - Updated hourly to help detect potential accumulation or distribution phases

### **Design Assumptions**

The application is optimized for long-term investing:

- Focus on higher timeframes (weekly data)
- Limited need for high-frequency ingestion (daily batches are sufficient)
- Separation of data sources:
  - market data (daily)
  - blockchain data (hourly)

This design ensures that the data pipeline directly supports the analytical goals of the application.

## **Tech Stack**

**Languages, Frameworks and Environments:**

    > Python
    > SQL
    > Docker / Docker Compose
    > Streamlit
    > GitHub Actions

**Data Engineering and Orchestration:**

    > Apache Airflow
    > dbt
    > Snowflake

**Libraries and Packages:**

    > pandas
    > numpy
    > plotly
    > snowflake-connector-python

**Monitoring (not included in the architecture graph):**

    > Prometheus
    > Grafana
    

## **Getting Started**

``` bash
git clone https://github.com/your-username/bitcoin-investing-tool
cd bitcoin-investing-tool

cp .env.example .env

docker compose up --build
```

## **Project Structure**

Below is a simplified overview of the project structure to help navigate the codebase:

``` bash
bitcoin-investing-tool/
│
├── airflow/                   # Workflow orchestration (Apache Airflow)
│   ├── dags/                  # DAG definitions
│   ├── Dockerfile             # Airflow container setup
│   └── docker-compose.yml     # Local orchestration environment
│
├── ingestion/                 # Market data ingestion (Binance API)
│   ├── binance_client.py        # API client for fetching market data from Binance
│   ├── snowflake_service.py     # Handles watermark retrieval and data loading into Snowflake
│   └── load_binance_ohlc.py     # Orchestrates OHLC ingestion using Binance client and Snowflake service
│
├── dbt/                       # Data transformation layer (ELT)
│   ├── models/
│   │   ├── stg/                   # Raw data cleaning and normalization
│   │   │   ├── blockchain/          # On-chain data transformations
│   │   │   └── market/              # Market data (Binance) transformations
│   │   ├── int/                   # Reusable intermediate transformations
│   │   │   └── market/
│   │   └── marts/                 # Final analytical data layer
│   │       ├── blockchain/
│   │       └── market/
│   ├── macros/                  # Reusable SQL logic
│   ├── seeds/                   # Static data loaded into warehouse
│   └── tests/                   # Data quality checks
│
├── app/                       # Streamlit application (serving layer)
│   ├── charts/                  # Visualizations
│   ├── components/              # UI sections
│   ├── logic/                   # Market summary features
│   ├── services/                # Data access layer (Snowflake)
│   ├── styles/                  # Styling (CSS)
│   └── streamlit_app.py         # Entry point
│
├── shared/                    # Shared utilities (Snowflake client)
│
└── README.md
```

