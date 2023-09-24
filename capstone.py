from datetime import timedelta,datetime
from airflow import DAG

from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.python_operator import PythonOperator
from pyspark.sql import SparkSession
from airflow.operators.email_operator import EmailOperator

default_args={
        'owner':'aniljat',
        'start_date':datetime(2023,9,20),
        'retries':5,
        'retry_delay':timedelta(minutes=5)
        }
dags=DAG(
        'Real_Estate_Data_Pipeline',
        default_args=default_args,
        description='analysis Real Estate data with saprk airflow',
        schedule_interval='* * * * *',
        catchup=False,
        tags=['analysis RealEstate Data']
        )
def fun1():
    spark=SparkSession.builder.appName("Spark Dataframe").getOrCreate()
    city_data=spark.read.csv("hdfs://localhost:9000/data/dataset/City_time_series.csv",header=True)
    city_crossWalk_data=spark.read.csv("hdfs://localhost:9000/data/dataset/cities_crosswalk.csv",header=True)
    city_data.createOrReplaceTempView("city")
    city_crossWalk_data.createOrReplaceTempView("city_crosswalk")
    df = spark.sql(""" SELECT
        c2.regionname as Region,
        c1.City,
        c1.County,
        c1.State,
        YEAR(c2.Date) AS Year,
        round(avg(c2.ZHVI_AllHomes) ,2) as `property price by ZHVI`,
        round(avg(c2.ZHVI_AllHomes) ,2) as `property price by ZRI`


    FROM
        city_crosswalk AS c1
    INNER JOIN
        city AS c2
    ON
        c1.Unique_City_ID = c2.regionname
    GROUP BY
        c2.regionname, c1.City, c1.County, c1.State,c2.date""")
    df = df.na.drop(subset=['property price by ZHVI ', 'property price by ZRI'])
    df = df.dropDuplicates()
    df = df.coalesce(1)
    df.write.mode("overwrite").option("header",True).csv("hdfs://localhost:9000/Avg_Property_Price")

def fun2():
    df2 = spark.sql("""
    WITH RegionAverages AS (
    SELECT
        c2.regionname AS Region,
        ROUND(AVG(c2.ZHVI_ALLHomes), 2) AS `ZHVI Property Price`
    FROM
        city AS c2
    GROUP BY
        c2.regionname
    )
    SELECT
    Region,
    `ZHVI Property Price`
    FROM (
    SELECT
        Region,
        `ZHVI Property Price`,
        DENSE_RANK() OVER (ORDER BY `ZHVI Property Price` DESC) AS Rank
    FROM
        RegionAverages
    ) RankedRegions
    WHERE
    Rank <= 10
    order by `ZHVI Property Price` desc""")
    df2 = df2.coalesce(1)
    df2.write.mode("overwrite").option("header",True).csv("hdfs://localhost:9000/Top_Regions_ZHVI")

def fun3():
    df3 = spark.sql("""
    WITH RegionAverages AS (
    SELECT
        c2.regionname AS Region,
        ROUND(AVG(c2.ZRI_ALLHomes), 2) AS `ZRI Property Price`
    FROM
        city AS c2
    GROUP BY
        c2.regionname
    )
    SELECT
    Region,
    `ZRI Property Price`
    FROM (
    SELECT
        Region,
        `ZRI Property Price`,
        DENSE_RANK() OVER (ORDER BY `ZRI Property Price` DESC) AS Rank
    FROM
        RegionAverages
    ) RankedRegions
    WHERE
    Rank <= 10
    order by `ZRI Property Price` desc""")
    df3 = df3.coalesce(1)
    df3.write.mode("overwrite").option("header",True).csv("hdfs://localhost:9000/Top_Regions_ZRI")


send_email = EmailOperator(
        task_id='send_email',
        to='anilkumarjat06@gmail.com',
        subject='ingestion complete',
        html_content="task done vrify email",
        dag=dags)
start_task=DummyOperator(task_id='start_task',dag=dags)
end_task=DummyOperator(task_id='end_task',dag=dags)
spark_task1=PythonOperator(task_id='Avg_Property_Price',python_callable=fun1,dag=dags)
spark_task2=PythonOperator(task_id='Top_Regions_ZHVI',python_callable=fun2,dag=dags)
spark_task3=PythonOperator(task_id='Top_Regions_ZRI',python_callable=fun3,dag=dags)
start_task>>[spark_task1,spark_task2,spark_task3]>>end_task>>send_email
















