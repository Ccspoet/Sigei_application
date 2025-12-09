
import streamlit as st
import pandas as pd
from requests import get
from bs4 import BeautifulSoup as bs
import base64
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import sqlite3
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="CoinAfrique Scraper", layout="wide")

# --- APP HEADER & DESCRIPTION (RESTORED) ---
st.markdown("<h1 style='text-align: center; color: black;'>MY DATA APP - Coinafrique</h1>", unsafe_allow_html=True)

st.markdown('''
This app performs webscraping of data from Coinafrique across multiple pages.
You can scrape with BeautifulSoup, download raw WebScraper exports, view a cleaned dashboard, and give feedback.
* **Python libraries:** base64, pandas, streamlit, requests, bs4, sqlite3
* **Data source:** https://sn.coinafrique.com
''')

# --- HELPER FUNCTIONS ---
def add_bg_from_local(image_file):
    if os.path.exists(image_file):
        with open(image_file, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read())
        st.markdown(
        f'''
        <style>
        .stApp {{
            background-image: url(data:image/{"jpg"};base64,{encoded_string.decode()});
            background-size: cover
        }}
        </style>
        ''',
        unsafe_allow_html=True
        )

def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

def load(dataframe, title, key, key1):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(title, key=key1):
            st.subheader(f"{title}")
            st.write(f"Dimensions: {dataframe.shape[0]} rows x {dataframe.shape[1]} columns")
            st.dataframe(dataframe.head(100)) 
            
            csv = convert_df(dataframe)
            st.download_button(
                label="Download Full CSV", 
                data=csv, 
                file_name=f'{title.replace(" ", "_")}.csv', 
                mime='text/csv', 
                key=key
            )

def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# --- OPTIMIZED DATA LOADER (CACHED) ---
@st.cache_data
def load_csv_data(filename):
    if os.path.exists(filename):
        try:
            return pd.read_csv(filename)
        except Exception as e:
            return pd.DataFrame()
    return pd.DataFrame()

# --- OPTIMIZED DASHBOARD FUNCTION (LITE) ---
def plot_category_stats_lite(df, category_name):
    st.markdown(f"### Analysis: {category_name}")
    
    if df.empty:
        st.warning("No data available.")
        return

    # 1. SMART COLUMN DETECTION
    price_col = next((c for c in df.columns if 'price' in c.lower() or 'prix' in c.lower()), None)
    possible_addr = ['address', 'location', 'ville', 'lieu', 'adresse', 'region']
    address_col = next((c for c in df.columns if c.lower().strip() in possible_addr), None)
    possible_names = ['type_item', 'type_clothes', 'type_shoes', 'name', 'description', 'titre']
    item_col = next((c for c in df.columns if c.lower().strip() in possible_names), df.columns[0])

    # 2. FAST DATA CLEANING
    if price_col:
        df['clean_price'] = pd.to_numeric(
            df[price_col].astype(str).str.replace(r'[^\d]', '', regex=True), 
            errors='coerce'
        )
        df_clean = df.dropna(subset=['clean_price'])
    else:
        df_clean = df

    # 3. METRICS
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Items", df.shape[0])
    if price_col and not df_clean.empty:
        m2.metric("Avg Price", f"{int(df_clean['clean_price'].mean()):,} CFA")
        m3.metric("Max Price", f"{int(df_clean['clean_price'].max()):,} CFA")

    st.markdown("---")

    # 4. PLOTS
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top Locations")
        if address_col:
            st.bar_chart(df[address_col].value_counts().head(10))
        else:
            st.info(f"Address column not found.")

    with c2:
        st.subheader(f"Top Items ({item_col})")
        st.bar_chart(df[item_col].value_counts().head(10))

    st.markdown("---")
    
    # 5. PRICE DISTRIBUTION
    st.subheader("Price Distribution")
    if price_col and not df_clean.empty:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.hist(df_clean['clean_price'], bins=30, color='skyblue', edgecolor='black')
        ax.set_title("Price Range Distribution")
        ax.set_xlabel("Price (CFA)")
        ax.grid(axis='y', alpha=0.5)
        st.pyplot(fig)
        plt.close(fig)
    else:
        st.info("No valid price data available for plotting.")

# --- SCRAPING FUNCTION ---
def scrape_data(url_base, table_name, db_name, csv_name, user_pages, max_limit):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute(f'''CREATE TABLE IF NOT EXISTS {table_name} (type_item TEXT, price TEXT, address TEXT, image_link TEXT)''')
    
    actual_pages = min(user_pages, max_limit)
    progress_text = f"Scraping {table_name} (Target: {actual_pages} pages)..."
    my_bar = st.progress(0, text=progress_text)
    
    for index in range(1, actual_pages + 1):
        try:
            res = get(f'{url_base}?page={index}')
            soup = bs(res.content, 'html.parser')
            containers = soup.find_all('div', 'col s6 m4 l3')
            for container in containers:
                try:
                    t = container.find('p', 'ad__card-description').text.strip()
                    p = container.find('p', 'ad__card-price').text.replace('CFA', '').replace(' ', '')
                    a = container.find('p', 'ad__card-location').span.text.strip()
                    i = container.find('img', 'ad__card-img').get('src')
                    c.execute(f'INSERT INTO {table_name} VALUES(?,?,?,?)', (t, p, a, i))
                except: pass
            conn.commit()
        except: pass
        my_bar.progress(index / actual_pages, text=f"Scraping page {index}/{actual_pages}")
        
    df = pd.read_sql_query(f'SELECT * FROM {table_name}', conn)
    conn.close()
    my_bar.empty()
    
    if not df.empty:
        df.drop_duplicates(inplace=True)
        df.to_csv(csv_name, index=False)
    return df

# --- FUNCTION: LOAD USER FILES ---
def load_my_scraped_files():
    st.markdown("<h3 style='text-align: center;'>My Local Scraped Files</h3>", unsafe_allow_html=True)
    files = [
        ("men_clothes.csv", "Men's Clothes", "k1", "b1"), 
        ("men_shoes.csv", "Men's Shoes", "k2", "b2"),
        ("children_clothes.csv", "Children's Clothes", "k3", "b3"),
        ("children_shoes.csv", "Children's Shoes", "k4", "b4")
    ]
    
    for filename, title, k, b in files:
        df = load_csv_data(filename)
        if not df.empty:
            load(df, title, k, b)
            st.write("---")
        else:
            st.warning(f"File '{filename}' not found in project folder.")

# --- MAIN APP LOGIC ---
st.sidebar.header('User Input Features')

# Slider capped at 120, but scraping logic limits children items to 22/8 automatically
Pages = st.sidebar.slider('Pages to scrape', 1, 120, 1)

Choices = st.sidebar.selectbox('Options', [
    'Scrape data using beautifulSoup', 
    'Download scraped data', 
    'Load My Scraped Files', 
    'Dashbord of the data', 
    'Evaluate the App'
])

add_bg_from_local('img_file3.jpg') 
local_css('style.css')  

# 1. SCRAPE
if Choices == 'Scrape data using beautifulSoup':
    st.info(f"Scraping started. Max pages set to user input ({Pages}), capped by category limits.")
    
    st.markdown("### 1. Men's Clothes")
    df_mc = scrape_data('https://sn.coinafrique.com/categorie/vetements-homme', 
                        'mens_clothes_tab', 'mens_clothes.db', 'mens_clothes_clean_data.csv', Pages, 119)
    load(df_mc, 'Men Clothes Data', 'scr_dl_1', 'scr_btn_1')

    st.markdown("### 2. Men's Shoes")
    df_ms = scrape_data('https://sn.coinafrique.com/categorie/chaussures-homme', 
                        'mens_shoes_tab', 'mens_shoes.db', 'mens_shoes_clean_data.csv', Pages, 119)
    load(df_ms, 'Men Shoes Data', 'scr_dl_2', 'scr_btn_2')

    st.markdown("### 3. Children's Clothes")
    df_cc = scrape_data('https://sn.coinafrique.com/categorie/vetements-enfants', 
                        'children_clothes_tab', 'children_clothes.db', 'children_clothes_clean_data.csv', Pages, 22)
    load(df_cc, 'Children Clothes Data', 'scr_dl_3', 'scr_btn_3')

    st.markdown("### 4. Children's Shoes")
    df_cs = scrape_data('https://sn.coinafrique.com/categorie/chaussures-enfants', 
                        'children_shoes_tab', 'children_shoes.db', 'children_shoes_clean_data.csv', Pages, 8)
    load(df_cs, 'Children Shoes Data', 'scr_dl_4', 'scr_btn_4')

# 2. DOWNLOAD SCRAPED
elif Choices == 'Download scraped data': 
    st.header("Download Recently Scraped Data")
    files = [
        ('mens_clothes_clean_data.csv', 'Mens Clothes Data', 'dl_1', 'btn_1'),
        ('mens_shoes_clean_data.csv', 'Mens Shoes Data', 'dl_2', 'btn_2'),
        ('children_clothes_clean_data.csv', 'Children Clothes Data', 'dl_3', 'btn_3'),
        ('children_shoes_clean_data.csv', 'Children Shoes Data', 'dl_4', 'btn_4')
    ]
    for f, title, k, b in files:
        df = load_csv_data(f)
        if not df.empty:
            load(df, title, k, b)
            st.write("---")
        else:
            st.warning(f"File {f} not found. Please scrape data first.")

# 3. LOAD LOCAL FILES
elif Choices == 'Load My Scraped Files':
    load_my_scraped_files()

# 4. DASHBOARD
elif  Choices == 'Dashbord of the data': 
    st.header("Dashboard Analytics")
    tab1, tab2, tab3, tab4 = st.tabs(["Men's Clothes", "Men's Shoes", "Kids Clothes", "Kids Shoes"])
    
    files_map = {
        "Men's Clothes": ["men_clothes.csv", "mens_clothes_clean_data.csv"],
        "Men's Shoes": ["men_shoes.csv", "mens_shoes_clean_data.csv"],
        "Kids Clothes": ["children_clothes.csv", "children_clothes_clean_data.csv"],
        "Kids Shoes": ["children_shoes.csv", "children_shoes_clean_data.csv"]
    }

    def safe_plot(tab, name, filename_list):
        with tab:
            df = pd.DataFrame()
            used_file = ""
            for fname in filename_list:
                if os.path.exists(fname):
                    df = load_csv_data(fname)
                    used_file = fname
                    break
            
            if not df.empty:
                st.caption(f"Visualizing data from: {used_file}")
                plot_category_stats_lite(df, name)
            else:
                st.warning(f"No data found for {name}. (Looked for: {', '.join(filename_list)})")

    safe_plot(tab1, "Men's Clothes", files_map["Men's Clothes"])
    safe_plot(tab2, "Men's Shoes", files_map["Men's Shoes"])
    safe_plot(tab3, "Kids Clothes", files_map["Kids Clothes"])
    safe_plot(tab4, "Kids Shoes", files_map["Kids Shoes"])

# 5. EVALUATE
else:
    st.markdown("<h3 style='text-align: center;'>Give your Feedback</h3>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.link_button("Kobo Evaluation Form", "https://ee.kobotoolbox.org/x/yc2vAerV")
    with col2:
        st.link_button("Google Forms Evaluation", "https://docs.google.com/forms/d/e/1FAIpQLSdgKBZpH9Lj6Ot0_4HT41gvD0yNpKSOjw3tOhih5uL5p5aWiQ/viewform?usp=header")
    