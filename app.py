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

# Очистка числовых полей
def parse_price(value):
    try:
        return float(str(value).replace("грн.", "").replace(",", ".").replace(" ", "").strip())
    except:
        return None

price_columns = [col for col in df.columns if "_цена" in col]
for col in price_columns:
    df[col] = df[col].apply(parse_price)

df["Итого продаж"] = df["Итого продаж"].apply(parse_price)
df["Средняя цена продажи"] = df["Средняя цена продажи"].apply(parse_price)


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

tab1, tab2, tab3 = st.tabs(["📈 Цены по товарам", "📊 Итоги по подкатегориям", "📉 Изменение цен по подкатегориям"])

with tab1:
    st.title("📈 Анализ изменения цен")

    if "subcategory" not in df.columns:
        st.error("❌ Колонка 'subcategory' не найдена.")
        st.stop()

    subcat = st.selectbox("Подкатегория", df["subcategory"].dropna().unique())
    filtered = df[df["subcategory"] == subcat]

    st.dataframe(filtered[[
        "Артикул", "title", "subcategory",
        "Первая цена за период (recalc)",
        "Последняя цена за период (recalc)",
        "Изменение цены в гривнах (recalc)",
        "Изменение цены % (recalc)"
    ]])


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

with tab3:
    st.title("Динамика цен по подкатегориям")

    # Группировка по подкатегориям
    df_grouped = df.dropna(subset=["subcategory"]).groupby("subcategory").agg(
        Среднее_изменение_цены_проц=("Изменение цены % (recalc)", "mean"),
        Макс_рост_цены_грн=("Изменение цены в гривнах (recalc)", "max"),
        Мин_падение_цены_грн=("Изменение цены в гривнах (recalc)", "min"),
        Товаров_в_подкатегории=("Артикул", "count")
    ).round(2).reset_index()

    # KPI
    col1, col2, col3 = st.columns(3)
    col1.metric("Средний рост цен", f"{df_grouped['Среднее_изменение_цены_проц'].mean():.2f}%")
    col2.metric("Макс. рост цены (грн)", f"{df_grouped['Макс_рост_цены_грн'].max():.2f} грн")
    col3.metric("Мин. падение цены (грн)", f"{df_grouped['Мин_падение_цены_грн'].min():.2f} грн")

    # 📋 Подробности
    st.markdown("### 📋 Подробности по подкатегориям")
    st.dataframe(df_grouped)

    # ⚠️ Кандидаты на повышение цены
    st.markdown("### Подкатегории с падением или отсутствием роста цен")
    min_items = 5
    candidates = df_grouped[
        (df_grouped["Среднее_изменение_цены_проц"] < 1) &
        (df_grouped["Товаров_в_подкатегории"] > min_items)
    ].copy()

    # Выручка: до и после +10%
    potentials = (
        df[df["subcategory"].isin(candidates["subcategory"])]
        .groupby("subcategory", as_index=False)["Итого продаж"]
        .sum()
        .rename(columns={"Итого продаж": "Итого продаж (до)"})
    )
    potentials["Итого продаж (если +10%)"] = (potentials["Итого продаж (до)"] * 1.10).round(0)
    potentials["Потенциал роста при +10%"] = (
        potentials["Итого продаж (если +10%)"] - potentials["Итого продаж (до)"]
    ).round(0)

    # Средняя цена продажи: до и после +10%
    avg_prices = (
        df[df["subcategory"].isin(candidates["subcategory"])]
        .groupby("subcategory", as_index=False)["Средняя цена продажи"]
        .mean()
        .rename(columns={"Средняя цена продажи": "Средняя цена (до)"})
    )
    avg_prices["Средняя цена (если +10%)"] = (avg_prices["Средняя цена (до)"] * 1.10).round(2)

    # Объединение
    candidates = candidates.merge(potentials, on="subcategory", how="left")
    candidates = candidates.merge(avg_prices, on="subcategory", how="left")

    # Вывод
    st.dataframe(candidates[[
        "subcategory",
        "Среднее_изменение_цены_проц",
        "Товаров_в_подкатегории",
        "Средняя цена (до)",
        "Средняя цена (если +10%)",
        "Итого продаж (до)",
        "Итого продаж (если +10%)",
        "Потенциал роста при +10%"
    ]].sort_values("Потенциал роста при +10%", ascending=False))

    # Общий итог
    total_gain = candidates["Потенциал роста при +10%"].sum()
    st.markdown(f"💰 Потенциальная суммарная прибавка к выручке: `{total_gain:,.0f} грн`")

    # 📊 Графики
    fig3 = px.bar(
        df_grouped.sort_values("Среднее_изменение_цены_проц", ascending=False),
        x="subcategory",
        y="Среднее_изменение_цены_проц",
        labels={"Среднее_изменение_цены_проц": "Средний рост, %"},
        title="📊 Среднее изменение цены по подкатегориям",
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("### 🔼 Топ-5 подкатегорий по росту цен")
    fig4 = px.bar(
        df_grouped.sort_values("Среднее_изменение_цены_проц", ascending=False).head(5),
        x="subcategory",
        y="Среднее_изменение_цены_проц",
        color="Среднее_изменение_цены_проц",
        labels={"Среднее_изменение_цены_проц": "%"},
    )
    st.plotly_chart(fig4, use_container_width=True)

    st.markdown("### 🔽 Топ-5 подкатегорий по снижению цен")
    fig5 = px.bar(
        df_grouped.sort_values("Среднее_изменение_цены_проц", ascending=True).head(5),
        x="subcategory",
        y="Среднее_изменение_цены_проц",
        color="Среднее_изменение_цены_проц",
        labels={"Среднее_изменение_цены_проц": "%"},
    )
    st.plotly_chart(fig5, use_container_width=True)
