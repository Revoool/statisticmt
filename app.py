import pandas as pd
import streamlit as st
import plotly.express as px

# ========================
# основная таблица
# ========================

column_names = [
    "Артикул", "Поставщик", "title", "category", "subcategory", "закупочная цена", "Средняя цена продажи"
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
# интерфейс
# ========================

st.set_page_config(page_title="📊 Аналитика", layout="wide")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Цены по товарам",
    "📊 Итоги по подкатегориям",
    "📉 Изменение цен по подкатегориям",
    "📦 Итоги по поставщикам",
    "📋 Анализ по поставщикам",
    "📚 Общая аналитика"
])



with tab1:
    st.title("📈 Анализ изменения цен")

    if "subcategory" not in df.columns:
        st.error("❌ Колонка 'subcategory' не найдена.")
        st.stop()

    subcat = st.selectbox("Подкатегория", df["subcategory"].dropna().unique())
    filtered = df[df["subcategory"] == subcat]

    st.dataframe(filtered[[
        "Артикул", 
        "Поставщик",
        "title", 
        "subcategory",
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

    df_grouped = df.dropna(subset=["subcategory"]).groupby("subcategory").agg(
        Среднее_изменение_цены_проц=("Изменение цены % (recalc)", "mean"),
        Макс_рост_цены_грн=("Изменение цены в гривнах (recalc)", "max"),
        Мин_падение_цены_грн=("Изменение цены в гривнах (recalc)", "min"),
        Товаров_в_подкатегории=("Артикул", "count")
    ).round(2).reset_index()

    col1, col2, col3 = st.columns(3)
    col1.metric("Средний рост цен", f"{df_grouped['Среднее_изменение_цены_проц'].mean():.2f}%")
    col2.metric("Макс. рост цены (грн)", f"{df_grouped['Макс_рост_цены_грн'].max():.2f} грн")
    col3.metric("Мин. падение цены (грн)", f"{df_grouped['Мин_падение_цены_грн'].min():.2f} грн")

    st.markdown("### 📋 Подробности по подкатегориям")
    st.dataframe(df_grouped)

    st.markdown("### Подкатегории с падением или отсутствием роста цен")
    min_items = 5
    candidates = df_grouped[
        (df_grouped["Среднее_изменение_цены_проц"] < 1) &
        (df_grouped["Товаров_в_подкатегории"] > min_items)
    ].copy()

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

    avg_prices = (
        df[df["subcategory"].isin(candidates["subcategory"])]
        .groupby("subcategory", as_index=False)["Средняя цена продажи"]
        .mean()
        .rename(columns={"Средняя цена продажи": "Средняя цена (до)"})
    )
    avg_prices["Средняя цена (если +10%)"] = (avg_prices["Средняя цена (до)"] * 1.10).round(2)

    candidates = candidates.merge(potentials, on="subcategory", how="left")
    candidates = candidates.merge(avg_prices, on="subcategory", how="left")

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

    total_gain = candidates["Потенциал роста при +10%"].sum()
    st.markdown(f"💰 Потенциальная суммарная прибавка к выручке: `{total_gain:,.0f} грн`")

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


with tab4:
    st.title("📋 Анализ по поставщикам")

    df_summary = pd.read_csv("Summar - Сводная vendor.csv")

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
        x="Популярные поставщики",
        y="Общая прибыль",
        title="📦 Прибыль по поставщику",
        labels={"Общая прибыль": "грн"},
    )
    st.plotly_chart(fig2)


# with tab4:
#     st.title("📦 Итоги по поставщикам")

#     try:
#         df_sup = pd.read_csv("Summar - Общая сводная.csv", sep=",", dtype=str)

#         def parse_price(val):
#             try:
#                 return float(str(val).replace("грн.", "").replace(",", ".").replace(" ", "").strip())
#             except:
#                 return None

#         df_sup["Итого продаж"] = df_sup["Итого продаж"].apply(parse_price)
#         df_sup["Средняя цена продажи"] = df_sup["Средняя цена продажи"].apply(parse_price)
#         df_sup["закупочная цена"] = df_sup["закупочная цена"].apply(parse_price)

#         df_sup = df_sup.dropna(subset=["Поставщик"])
        
#         grouped_suppliers = df_sup.groupby("Поставщик").agg(
#             Товаров=("Артикул", "count"),
#             Сумма_продаж=("Итого продаж", "sum"),
#             Средняя_цена_продажи=("Средняя цена продажи", "mean"),
#             Средняя_закупка=("закупочная цена", "mean"),
#         ).reset_index()

#         grouped_suppliers["Средняя_маржа"] = (
#             grouped_suppliers["Средняя_цена_продажи"] - grouped_suppliers["Средняя_закупка"]
#         ).round(2)

#         selected_vendor = st.selectbox("Выберите поставщика", df_sup["Поставщик"].unique())
#         st.dataframe(df_sup[df_sup["Поставщик"] == selected_vendor])

#         st.markdown("### Топ-20 поставщиков по выручке")
#         st.dataframe(grouped_suppliers.sort_values("Сумма_продаж", ascending=False))


#         st.markdown("### Топ-10 поставщиков по средней марже")
#         fig_margins = px.bar(
#             grouped_suppliers.sort_values("Средняя_маржа", ascending=False).head(10),
#             x="Поставщик",
#             y="Средняя_маржа",
#             title="🏆 Средняя маржа по поставщикам",
#             labels={"Средняя_маржа": "грн"},
#         )
#         st.plotly_chart(fig_margins)
        
#         fig_supplier_profit = px.bar(
#             grouped_suppliers.sort_values("Сумма_продаж", ascending=False).head(20),
#             x="Поставщик",
#             y="Сумма_продаж",
#             title="💰 Топ-20 поставщиков по выручке",
#             labels={"Сумма_продаж": "грн"},
#         )
#         st.plotly_chart(fig_supplier_profit)

#     except Exception as e:
#         st.error(f"Ошибка при обработке данных по поставщикам: {e}")



with tab5:
    st.title("📋 Анализ по поставщикам")

    if "Поставщик" not in df.columns:
        st.warning("Нет данных по поставщикам.")
        st.stop()

    df_vendor_grouped = df.dropna(subset=["Поставщик"]).groupby("Поставщик").agg(
        Среднее_изменение_цены_проц=("Изменение цены % (recalc)", "mean"),
        Макс_рост_цены_грн=("Изменение цены в гривнах (recalc)", "max"),
        Мин_падение_цены_грн=("Изменение цены в гривнах (recalc)", "min"),
        Товаров_у_поставщика=("Артикул", "count")
    ).round(2).reset_index()

    col1, col2, col3 = st.columns(3)
    col1.metric("Средний рост цен у поставщиков", f"{df_vendor_grouped['Среднее_изменение_цены_проц'].mean():.2f}%")
    col2.metric("Макс. рост цены (грн)", f"{df_vendor_grouped['Макс_рост_цены_грн'].max():.2f} грн")
    col3.metric("Мин. падение цены (грн)", f"{df_vendor_grouped['Мин_падение_цены_грн'].min():.2f} грн")

    st.markdown("### 📋 Подробности по поставщикам")
    st.dataframe(df_vendor_grouped)

    min_items = 5
    vendor_candidates = df_vendor_grouped[
        (df_vendor_grouped["Среднее_изменение_цены_проц"] < 1) &
        (df_vendor_grouped["Товаров_у_поставщика"] > min_items)
    ].copy()

    vendor_potentials = (
        df[df["Поставщик"].isin(vendor_candidates["Поставщик"])]
        .groupby("Поставщик", as_index=False)["Итого продаж"]
        .sum()
        .rename(columns={"Итого продаж": "Итого продаж (до)"})
    )
    vendor_potentials["Итого продаж (если +10%)"] = (vendor_potentials["Итого продаж (до)"] * 1.10).round(0)
    vendor_potentials["Потенциал роста при +10%"] = (
        vendor_potentials["Итого продаж (если +10%)"] - vendor_potentials["Итого продаж (до)"]
    ).round(0)

    avg_vendor_prices = (
        df[df["Поставщик"].isin(vendor_candidates["Поставщик"])]
        .groupby("Поставщик", as_index=False)["Средняя цена продажи"]
        .mean()
        .rename(columns={"Средняя цена продажи": "Средняя цена (до)"})
    )
    avg_vendor_prices["Средняя цена (если +10%)"] = (avg_vendor_prices["Средняя цена (до)"] * 1.10).round(2)

    vendor_candidates = vendor_candidates.merge(vendor_potentials, on="Поставщик", how="left")
    vendor_candidates = vendor_candidates.merge(avg_vendor_prices, on="Поставщик", how="left")

    st.markdown("### 📈 Поставщики с возможным ростом")
    st.dataframe(vendor_candidates[[
        "Поставщик",
        "Среднее_изменение_цены_проц",
        "Товаров_у_поставщика",
        "Средняя цена (до)",
        "Средняя цена (если +10%)",
        "Итого продаж (до)",
        "Итого продаж (если +10%)",
        "Потенциал роста при +10%"
    ]].sort_values("Потенциал роста при +10%", ascending=False))

    total_vendor_gain = vendor_candidates["Потенциал роста при +10%"].sum()
    st.markdown(f"💰 Потенциальная прибавка к выручке: `{total_vendor_gain:,.0f} грн`")

    st.markdown("### 🔼 Топ-5 поставщиков по росту цен")
    fig_vendor_up = px.bar(
        df_vendor_grouped.sort_values("Среднее_изменение_цены_проц", ascending=False).head(5),
        x="Поставщик",
        y="Среднее_изменение_цены_проц",
        color="Среднее_изменение_цены_проц",
        labels={"Среднее_изменение_цены_проц": "%"},
    )
    st.plotly_chart(fig_vendor_up, use_container_width=True)

    st.markdown("### 🔽 Топ-5 поставщиков по падению цен")
    fig_vendor_down = px.bar(
        df_vendor_grouped.sort_values("Среднее_изменение_цены_проц", ascending=True).head(5),
        x="Поставщик",
        y="Среднее_изменение_цены_проц",
        color="Среднее_изменение_цены_проц",
        labels={"Среднее_изменение_цены_проц": "%"},
    )
    st.plotly_chart(fig_vendor_down, use_container_width=True)


# with tab6:
#     st.title("📋 Анализ по поставщикам")

#     def clean_price_column(series):
#         return (
#             series.astype(str)
#             .str.replace(",", ".", regex=False)
#             .str.replace(r"[^\d\.]", "", regex=True)
#             .replace("", float("nan"))
#             .astype(float)
#         )

#     df["Средняя цена продажи"] = clean_price_column(df["Средняя цена продажи"])
#     df["закупочная цена"] = clean_price_column(df["закупочная цена"])

#     col1, col2, col3 = st.columns(3)
#     col1.metric("Всего уникальных товаров", df["Артикул"].nunique())
#     col2.metric("Средняя цена продажи", f"{df['Средняя цена продажи'].mean():.2f} грн")

#     st.markdown("### 📦 Количество товаров по категориям")
#     category_counts = df["category"].value_counts().reset_index()
#     category_counts.columns = ["Категория", "Количество"]

#     fig_category = px.bar(
#         category_counts.sort_values("Количество", ascending=False),
#         x="Категория",
#         y="Количество",
#         title="Количество товаров по категориям",
#     )
#     st.plotly_chart(fig_category, use_container_width=True)

#     st.markdown("### 💰 Средняя закупочная vs. продажная цена по подкатегориям")
#     by_subcat = df.groupby("subcategory").agg(
#         Средняя_цена_продажи=("Средняя цена продажи", "mean"),
#         Средняя_закупка=("закупочная цена", "mean")
#     ).dropna().round(2).reset_index()

#     fig_prices = px.bar(
#         by_subcat.melt(id_vars="subcategory", value_vars=["Средняя_цена_продажи", "Средняя_закупка"]),
#         x="subcategory",
#         y="value",
#         color="variable",
#         title="Средняя цена продажи vs. закупочная по подкатегориям",
#         labels={"value": "Цена", "subcategory": "Подкатегория", "variable": "Тип"},
#         barmode="group"
#     )
#     st.plotly_chart(fig_prices, use_container_width=True)

#     st.markdown("### 🏆 Топ-10 товаров по объему продаж")
#     top_sales = df[["title", "Итого продаж"]].dropna().sort_values("Итого продаж", ascending=False).head(10)

#     fig_top_products = px.bar(
#         top_sales,
#         x="title",
#         y="Итого продаж",
#         title="Топ-10 товаров по продажам",
#         labels={"Итого продаж": "грн", "title": "Товар"}
#     )
#     st.plotly_chart(fig_top_products, use_container_width=True)

