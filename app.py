import pandas as pd
import streamlit as st
import plotly.express as px

# ========================
# Загрузка и обработка основной таблицы
# ========================

column_names = [
    "Артикул", "title", "category", "subcategory", "закупочная цена", "Средняя цена продажи",
]

months = ["06.2024", "07.2024", "08.2024", "09.2024", "10.2024", "11.2024", "12.2024", "01.2025", "02.2025", "03.2025", "04.2025"]
for m in months:
    column_names.extend([f"{m}_шт", f"{m}_цена"])

column_names += ["всего проданно товара", "Закупочная цена всего", "Итого продаж",
                 "Первая цена за период", "Последняя цена за период", "Изменение цены в гривнах",
                 "Средняя цена за период", "MAX / MIN цена за период", "", "Всего месяцев с продажами (сезонность)",
                 "Тренд продаж", "Волатильность", "Месяц макс продаж"]

df = pd.read_csv("Summar - Общая сводная.csv", names=column_names, skiprows=1)

def parse_price(value):
    try:
        return float(str(value).replace("грн.", "").replace(",", ".").replace(" ", "").strip())
    except:
        return None

price_columns = [col for col in df.columns if "_цена" in col]
for col in price_columns:
    df[col] = df[col].apply(parse_price)

def get_first_price(row):
    for col in price_columns:
        if pd.notnull(row[col]):
            return row[col]
    return None

def get_last_price(row):
    for col in reversed(price_columns):
        if pd.notnull(row[col]):
            return row[col]
    return None

df["Первая цена за период (recalc)"] = df.apply(get_first_price, axis=1)
df["Последняя цена за период (recalc)"] = df.apply(get_last_price, axis=1)
df["Изменение цены в гривнах (recalc)"] = df["Последняя цена за период (recalc)"] - df["Первая цена за период (recalc)"]
df["Изменение цены % (recalc)"] = (df["Изменение цены в гривнах (recalc)"] / df["Первая цена за период (recalc)"] * 100).round(2)

# ========================
# Интерфейс Streamlit
# ========================

st.set_page_config(page_title="📊 Аналитика", layout="wide")

tab1, tab2 = st.tabs(["📈 Цены по товарам", "📊 Итоги по подкатегориям"])

with tab1:
    st.title("📈 Анализ изменения цен")
    st.markdown("Выберите подкатегорию товара и посмотрите, как изменялась цена в течение года.")

    if "subcategory" not in df.columns:
        st.error("❌ Колонка 'subcategory' не найдена.")
        st.stop()

    subcat = st.selectbox("Выберите подкатегорию", df["subcategory"].dropna().unique())
    filtered = df[df["subcategory"] == subcat]

    st.dataframe(filtered[[
        "Артикул", "title", "subcategory",
        "Первая цена за период (recalc)",
        "Последняя цена за период (recalc)",
        "Изменение цены в гривнах (recalc)",
        "Изменение цены % (recalc)"
    ]])

    fig = px.bar(
        filtered,
        x="title",
        y="Изменение цены % (recalc)",
        title="Изменение цены (%) по товарам",
        labels={"Изменение цены % (recalc)": "% изменения"},
    )
    st.plotly_chart(fig)

with tab2:
    st.title("📊 Итоги по подкатегориям")

    df_summary = pd.read_csv("Summar - Сводная subcategory.csv")

    def clean_num(x):
        try:
            return float(str(x).replace(",", ".").replace(" ", "").replace("%", "").strip())
        except:
            return None

    num_cols = df_summary.columns[1:]
    for col in num_cols:
        df_summary[col] = df_summary[col].apply(clean_num)

    st.dataframe(df_summary)

    fig2 = px.bar(
        df_summary.sort_values("Общая прибыль", ascending=False),
        x="Популярные подкатегории",
        y="Общая прибыль",
        title="📦 Прибыль по подкатегориям",
        labels={"Общая прибыль": "грн"},
    )
    st.plotly_chart(fig2)
