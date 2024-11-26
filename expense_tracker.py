from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from io import BytesIO
import pandas as pd
import streamlit as st
import json

# authentication
endpoint = st.secrets['azure_endpoint']
key = st.secrets['azure_key']

# instantiate client
document_intelligence_client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))

# analyze receipt bytes
def analyze_receipt(receipt_bytes):
    with BytesIO(receipt_bytes) as f:
        # poll client for response
        poller = document_intelligence_client.begin_analyze_document("prebuilt-receipt", analyze_request=f, locale="en-US", content_type="application/octet-stream")

    # get result
    receipt_result: AnalyzeResult = poller.result()
    # parse result
    if receipt_result.documents:
        for receipt in receipt_result.documents:
            items_list = []
            if receipt.fields:
                # merchant
                merchant_name = receipt.fields.get("MerchantName")
                if merchant_name: merchant_name = merchant_name.get("valueString", None)
                merchant_address = receipt.fields.get("MerchantAddress")
                if merchant_address: merchant_address = merchant_address.get("content", None)
                transaction_date = receipt.fields.get("TransactionDate")
                if transaction_date: transaction_date = transaction_date.get("valueDate", None)
                # items
                items = receipt.fields.get("Items")
                if items:
                    for item in items.get("valueArray"):
                        item_description = item.get("valueObject").get("Description")
                        if item_description: item_description = item_description.get("valueString", None)
                        item_total_price = item.get("valueObject").get("TotalPrice", None)
                        if item_total_price: item_total_price = item_total_price.get("valueCurrency").get("amount", None)
                        items_list.append({
                            "item_name": item_description,
                            "item_value": item_total_price
                            })
                # totals
                subtotal = receipt.fields.get("Subtotal", None)
                if subtotal: subtotal = subtotal.get("valueCurrency").get("amount", None)
                tax = receipt.fields.get("TotalTax", None)
                if tax: tax = tax.get("valueCurrency").get("amount", None)
                total = receipt.fields.get("Total", None)
                if total: total = total.get("valueCurrency").get("amount", None)

    return merchant_name, merchant_address, transaction_date, items_list, subtotal, tax, total

# process receipt
def process_data(receipts_raw):
    receipts_list = []
    for receipt_raw in receipts_raw:
        receipt_bytes = receipt_raw.getvalue()
        merchant_name, merchant_address, transaction_date, items_array, subtotal, tax, total = analyze_receipt(receipt_bytes)

        # create receipt dict
        receipt_data = {
            'merchant_name': merchant_name,
            'merchant_address': merchant_address,
            'transaction_date': transaction_date,
            'items': items_array,
            'subtotal': subtotal,
            'tax': tax,
            'total': total
        }
        receipts_list.append(receipt_data)
    
    # store data
    st.session_state['data'] = receipts_list

# UI
def main():
    if 'widen' not in st.session_state:
        layout = 'centered'
    else:
        layout = 'wide' if st.session_state.widen else 'centered'

    st.set_page_config(layout=layout, page_title='Quanto Receipt Scanner', page_icon='🤗')

    st.title('Quanto Receipt Scanner')
    st.subheader('Instructions')
    st.markdown(
        """
        This tool uses Optical Character Recognition (OCR) to extract data from the documents you provide.\n
        Upload receipts and click **Analyze Documents** to generate a report.
        """
    )

    # file input
    receipts_raw = st.file_uploader('Receipts', type=['png','jpg','jpeg','pdf'], accept_multiple_files=True)
    st.button('Analyze Documents', on_click=process_data, args=[receipts_raw])

    # display data
    if 'data' in st.session_state:
        data = st.session_state['data']
        # dataframe/table
        df_list = []
        for receipt in data:
            # check if items exist
            if 'items' in receipt: df_list.append(pd.json_normalize(receipt, 'items', ['merchant_name', 'merchant_address', 'transaction_date']))
        df = pd.concat(df_list, ignore_index=True)
        st.dataframe(df)
        # json
        st.write('JSON data')
        st.write(data)

if __name__ == '__main__':
    main()