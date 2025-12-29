import streamlit as st
import pandas as pd
import re
import io

# --- إعدادات الصفحة ---
st.set_page_config(
    page_title="مدقق الرواتب - مصرف الرافدين",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS لتحسين العرض ---
st.markdown("""
<style>
    .main { direction: rtl; text-align: right; }
    .stAlert { direction: rtl; text-align: right; }
    div[data-testid="stMarkdownContainer"] p { font-size: 16px; }
    /* تنسيق الجداول */
    .stDataFrame { direction: ltr; } 
</style>
""", unsafe_allow_html=True)

# --- دوال المنطق ---
def find_columns(df):
    iban_col = None
    amount_col = None
    payer_col = None

    for col in df.columns:
        c_low = str(col).lower().strip()
        
        # البحث عن حساب المستفيد
        if (("beneficiary" in c_low) and ("account" in c_low or "acount" in c_low or "iban" in c_low)) and "payer" not in c_low:
            iban_col = col
            
        # البحث عن حساب الدافع
        if "payer" in c_low and ("account" in c_low or "acount" in c_low):
            payer_col = col
            
        # البحث عن المبلغ
        if "amount" in c_low or "مبلغ" in c_low or "راتب" in c_low:
            amount_col = col
            
    return iban_col, amount_col, payer_col

def clean_amount_val(val):
    val_str = str(val)
    clean = re.sub(r'[^\\d.]', '', val_str)
    try:
        return float(clean)
    except:
        return 0.0

def check_iban_mod97(iban):
    try:
        if not iban.startswith("IQ") or len(iban) != 23:
            return False
        rearranged = iban[4:] + iban[:4]
        numeric_iban = ""
        for char in rearranged:
            if char.isdigit(): numeric_iban += char
            else: numeric_iban += str(ord(char) - 55)
        return int(numeric_iban) % 97 == 1
    except: return False

# --- واجهة التطبيق ---
st.title("🏦 نظام تدقيق الرواتب (Streamlit)")
st.markdown("---")

uploaded_file = st.file_uploader("📂 اختر ملف الرواتب (Excel)", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file, dtype=str)
        df.columns = df.columns.str.strip()
        
        iban_col, amount_col, payer_col = find_columns(df)
        
        # عرض حالة الأعمدة
        c1, c2, c3 = st.columns(3)
        with c1:
            if iban_col: st.success(f"✅ المستفيد: {iban_col}")
            else: st.error("❌ لم نجد عمود المستفيد")
        with c2:
            if payer_col: st.success(f"✅ الدافع: {payer_col}")
            else: st.warning("⚠️ لا يوجد عمود Payer (اختياري)")
        with c3:
            if amount_col: st.success(f"✅ المبلغ: {amount_col}")
            else: st.error("❌ لم نجد عمود المبلغ")

        if not iban_col or not amount_col:
            st.stop()

        tab1, tab2 = st.tabs(["🔍 تقرير الفحص", "🛠️ تنظيف وتحميل"])

        # === التبويب 1: الفحص ===
        with tab1:
            if st.button("بدء الفحص", key="btn_audit"):
                
                critical_errors = [] # أخطاء قاتلة (أحمر)
                warnings_list = []   # تنبيهات فقط (أصفر)
                seen_ibans = {}      # لتتبع التكرار
                
                progress_bar = st.progress(0)
                
                for index, row in df.iterrows():
                    row_num = index + 2
                    progress_bar.progress((index + 1) / len(df))
                    
                    # 1. فحص المستفيد
                    raw_iban = str(row[iban_col])
                    
                    # --- التعديل الجديد: فحص الأحرف الصغيرة (Small Letters) ---
                    if re.search(r'[a-z]', raw_iban):
                         critical_errors.append(f"❌ [صف {row_num}] خطأ تنسيق: الايبان يحتوي على حروف صغيرة (Small Letters): {raw_iban}")
                    # -------------------------------------------------------

                    if " " in raw_iban:
                        warnings_list.append(f"⚠️ [صف {row_num}] مسافة زائدة في حساب المستفيد (سيتم حذفها عند التنظيف).")
                    
                    # تحويل النص للكبير الآن لغرض الفحص الرياضي
                    clean_iban = raw_iban.replace(" ", "").strip().upper()
                    
                    # أ) فحص الصحة الرياضية (قاتل)
                    if not check_iban_mod97(clean_iban):
                        critical_errors.append(f"❌ [صف {row_num}] حساب المستفيد خطأ (رياضياً أو طول الرقم): {clean_iban}")
                    
                    # ب) فحص التكرار (تنبيه فقط)
                    if clean_iban in seen_ibans:
                        warnings_list.append(f"📝 [صف {row_num}] تنبيه تكرار: هذا الحساب مكرر مع الصف {seen_ibans[clean_iban]}.")
                    else:
                        seen_ibans[clean_iban] = row_num

                    # 2. فحص الدافع
                    if payer_col:
                        raw_payer = str(row[payer_col])
                        
                        # --- التعديل الجديد: فحص الأحرف الصغيرة للدافع أيضاً ---
                        if re.search(r'[a-z]', raw_payer):
                             critical_errors.append(f"❌ [صف {row_num}] حساب الدافع يحتوي على حروف صغيرة: {raw_payer}")
                        # -----------------------------------------------------

                        if " " in raw_payer:
                            warnings_list.append(f"⚠️ [صف {row_num}] مسافة في حساب الدافع.")
                        
                        clean_payer = raw_payer.replace(" ", "").strip().upper()
                        if not check_iban_mod97(clean_payer):
                            critical_errors.append(f"❌ [صف {row_num}] حساب الدافع خطأ: {clean_payer}")
                            
                    # 3. فحص المبلغ
                    amt = clean_amount_val(row[amount_col])
                    if amt <= 0:
                        critical_errors.append(f"❌ [صف {row_num}] المبلغ صفر أو غير صالح.")

                # --- عرض النتائج ---
                
                # 1. عرض الأخطاء القاتلة (الأحمر)
                if len(critical_errors) > 0:
                    st.error(f"⛔ وجدنا {len(critical_errors)} أخطاء يجب إصلاحها يدوياً في الملف الأصلي:")
                    for err in critical_errors:
                        st.write(err)
                    st.markdown("---")
                else:
                    st.success("✅ لا توجد أخطاء رياضية أو حسابية.")

                # 2. عرض التنبيهات (الأصفر)
                if len(warnings_list) > 0:
                    st.warning(f"⚠️ ملاحظات وتنبيهات ({len(warnings_list)}) - (يمكن تجاهلها إذا كنت متأكداً):")
                    with st.expander("عرض قائمة التنبيهات (التكرار والمسافات)", expanded=False):
                        for warn in warnings_list:
                            st.write(warn)
                
                if len(critical_errors) == 0 and len(warnings_list) == 0:
                    st.balloons()

        # === التبويب 2: التنظيف ===
        with tab2:
            st.info("سيقوم هذا القسم بحذف المسافات وإصلاح صيغة المبالغ وتحويل الحروف للكبير ليكون الملف جاهزاً.")
            
            df_clean = df.copy()
            
            # تنظيف المستفيد
            df_clean[iban_col] = df_clean[iban_col].astype(str).str.replace(" ", "").str.strip().str.upper()
            
            # تنظيف الدافع
            if payer_col:
                df_clean[payer_col] = df_clean[payer_col].astype(str).str.replace(" ", "").str.strip().str.upper()
                
            # تنظيف المبلغ
            df_clean[amount_col] = df_clean[amount_col].apply(lambda x: f"{clean_amount_val(x):.0f}")
            
            st.dataframe(df_clean.head())
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_clean.to_excel(writer, index=False)
                
            st.download_button(
                label="📥 تحميل الملف الجاهز (Excel)",
                data=buffer,
                file_name="Salary_Ready_For_Notepad.xlsx",
                mime="application/vnd.ms-excel"
            )

    except Exception as e:
        st.error(f"حدث خطأ: {e}")
 
