import os
import ast
import re
import time
import psycopg2
from psycopg2 import sql
import streamlit as st
import openai
from openai import AssistantEventHandler
import math
from typing_extensions import override
from openai.types.beta.threads import Text, TextDelta
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
import logging
import datetime
import threading

from better_profanity import profanity
from decrypted_spam_words import load_spam_keywords

# Memuat variabel lingkungan dari .env file untuk pengaturan sensitif
load_dotenv()

# Memuat daftar kata spam dan kata kasar untuk filtering konten
spam_keywords = load_spam_keywords()
profanity.load_censor_words()

# Connection parameters for YugabyteDB
dbname = os.getenv("DBNAME")
host = os.getenv("DBHOST")
port = os.getenv("DBPORT")
user = os.getenv("DBUSER")
password = os.getenv("DBPASSWORD")

# Function to insert log data into the YugabyteDB


def insert_log_data(log_data):

    client_ip = st.query_params.client_ip
    # print("🚀 ~ file: chatbot_yugabyte.py:149 ~ client_ip:", client_ip)

    try:
        connection = psycopg2.connect(
            dbname=dbname, user=user, password=password, host=host, port=port
        )
        cursor = connection.cursor()

        # DONT REMOVE, THESE FOR INITIATE FIRST RUNNING
        # DONT REMOVE, THESE FOR INITIATE FIRST RUNNING
        # Create the chatbot_logs table
        # create_table_query = '''
        # CREATE TABLE IF NOT EXISTS chatbot_logs (
        #     id SERIAL PRIMARY KEY,
        #     branch TEXT,
        #     user_ip TEXT,
        #     nik TEXT,
        #     username TEXT,
        #     phone TEXT,
        #     user_message TEXT,
        #     assistant_response TEXT,
        #     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        # );
        # '''
        # cursor.execute(create_table_query)
        # connection.commit()
        # print("Table created successfully")
        # DONT REMOVE, THESE FOR INITIATE FIRST RUNNING
        # DONT REMOVE, THESE FOR INITIATE FIRST RUNNING

        # BUKA JIKA PAKAI INPUT BRANCH
        # insert_query = '''
        # INSERT INTO chatbot_logs (branch, user_ip, nik, username, phone, user_message, assistant_response)
        # VALUES (%s, %s, %s, %s, %s, %s, %s);
        # '''

        insert_query = """
        INSERT INTO chatbot_logs (user_ip, nik, username, phone, user_message, assistant_response)
        VALUES (%s, %s, %s, %s, %s, %s);
        """

        cursor.execute(
            insert_query,
            (
                # log_data["branch"],
                client_ip,
                # log_data["user_ip"],
                log_data["nik"],
                log_data["username"],
                log_data["phone"],
                log_data["user_message"],
                log_data["assistant_response"],
            ),
        )
        connection.commit()
        # print("Log data inserted successfully")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
    finally:
        if connection:
            cursor.close()
            connection.close()


# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# Function to update the log handler daily (interval-based)
def update_log_handler(logger):
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    log_filename = f"{current_date}.log"  # Log file format YYYY-MM-DD.log

    # Create a new file handler for the current day
    file_handler = logging.FileHandler(log_filename, mode="a")
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # Clear existing handlers and set the new handler
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(file_handler)


# Function to rotate log files at midnight daily using interval
def rotate_log_files():
    while True:
        # Update the log file handler at the start
        update_log_handler(logger)

        # Calculate the time until the next midnight
        now = datetime.datetime.now()
        midnight = datetime.datetime.combine(
            now.date() + datetime.timedelta(days=1), datetime.time.min
        )
        time_until_midnight = (midnight - now).seconds

        # Sleep until the next midnight, then rotate the log file
        time.sleep(time_until_midnight)


# Start the log rotation in a background thread
log_thread = threading.Thread(target=rotate_log_files, daemon=True)
log_thread.start()

# Define options for the dropdown
# options = ["", "J00 - Kantor Cabang Jakarta Salemba", "J11 - Kantor Cabang Tangerang Batuceper⁠", " ⁠K01 - Kantor Cabang Bekasi Kota"]

# Pengaturan konfigurasi tampilan halaman di Streamlit
st.set_page_config(
    page_title="Ngobrol Bersama IVA - BPJS Ketenagakerjaan",
    page_icon="./page_icon.png",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Initialize session state to store user data
if "nik" not in st.session_state:
    st.session_state["nik"] = ""
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "phone_number" not in st.session_state:
    st.session_state["phone_number"] = ""
if "conversation_started" not in st.session_state:
    st.session_state["conversation_started"] = False
if "client_ip" not in st.query_params:
    st.query_params["client_ip"] = ""
# Get client IP from query parameters
# if 'branch' not in st.session_state:
#     st.session_state['branch'] = ''  # Save the IP address in session state

if "response_in_progress" not in st.session_state:
    st.session_state["response_in_progress"] = False

if "response_processed" not in st.session_state:
    st.session_state["response_processed"] = False


class EventHandler(AssistantEventHandler):
    """
    Event handler for the assistant stream
    """

    @override
    def on_event(self, event):
        if event.event == "thread.run.requires_action":
            run_id = event.data.id
            self.handle_requires_action(event.data, run_id)

    @override
    def on_text_created(self, text: Text) -> None:
        try:
            st.session_state[
                f"code_expander_{len(st.session_state.text_boxes) - 1}"
            ].update(state="complete", expanded=False)
        except KeyError:
            pass

        cleaned_text = re.sub(r"【\d+:\d+†source】", "", text.value)
        st.session_state.text_boxes.append(st.empty())
        st.session_state.text_boxes[-1].info(cleaned_text)

    @override
    def on_text_delta(self, delta: TextDelta, snapshot: Text):
        st.session_state.text_boxes[-1].empty()
        if delta.value:
            cleaned_delta = re.sub(r"【\d+:\d+†source】", "", delta.value)
            st.session_state.assistant_text[-1] += cleaned_delta
        st.session_state.text_boxes[-1].info(
            "".join(st.session_state["assistant_text"][-1])
        )

    def on_text_done(self, text: Text):
        cleaned_text = re.sub(r"【\d+:\d+†source】", "", text.value)
        st.session_state.text_boxes.append(st.empty())
        st.session_state.assistant_text.append("")
        st.session_state.chat_history.append(("assistant", cleaned_text))

        # Prepare log data for YugabyteDB
        log_data = {
            # "branch": st.session_state['branch'],
            # "user_ip": st.session_state.get('ip_address', ''),
            "nik": st.session_state["nik"],
            "username": st.session_state["username"],
            "phone": st.session_state["phone_number"],
            "user_message": st.session_state.chat_history[-2][1],
            "assistant_response": cleaned_text,
        }

        # Insert log data into YugabyteDB
        insert_log_data(log_data)


key = os.getenv("OPENAI_API_KEY")
assistant_id = os.getenv("ASSISTANT_ID")
vect_id = os.getenv("VECTOR_STORE_ID")

client = OpenAI(api_key=key)

assistant = client.beta.assistants.update(
    assistant_id=assistant_id,
    tool_resources={"file_search": {"vector_store_ids": [vect_id]}},
)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "assistant_text" not in st.session_state:
    st.session_state.assistant_text = [""]

if "thread_id" not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id

if "text_boxes" not in st.session_state:
    st.session_state.text_boxes = []

logo = "./logobpjstk.png"
st.sidebar.image(image=logo, use_container_width=True)


# Membuat pola untuk mendeteksi kata-kata spam
def build_spam_pattern():
    variations = {
        "a": "[a@4^></]",
        "i": "[i1!|]",
        "g": "[g9]",
        "s": "[s$5]",
        "h": "[h#]",
        "t": "[t7]",
        "o": "[o0%]",
        "e": "[e3]",
        "k": "[kx]",
        "x": "[x><]",
        "u": "[uvµ]",
        "l": "[l1|!]",
        "m": "[mµ]",
    }
    # Membuat daftar pola kata dari spam_keywords dan variations
    patterns = []
    for word in spam_keywords:
        pattern = ""
        for char in word:
            var = variations.get(char, re.escape(char))
            pattern += var + "+"

        patterns.append(f"({pattern})")

    return re.compile("|".join(patterns), re.IGNORECASE)


def check_spam_keywords(text):
    spam_pattern = build_spam_pattern()

    joined_text = re.sub(r"\s+", "", text.lower())

    if re.search(spam_pattern, text) is not None:
        return True

    if re.search(spam_pattern, joined_text) is not None:
        return True

    return False

# Fungsi utama untuk mengecek apakah teks mengandung spam/kata kasar
def is_spam(text):
    combined_text = text.replace(" ", "")

    if profanity.contains_profanity(text) or profanity.contains_profanity(
        combined_text
    ):
        return True

    words = text.split()
    for word in words:
        if word.lower() in spam_keywords:
            return True

    return check_spam_keywords(text.lower()) or check_spam_keywords(
        combined_text.lower()
    )

def chat_interface():
    st.title("💬 IVA v1.0.3")
    st.chat_message("Assistant").write(
        f"""
        <div style="text-align: justify;">
            Halo 👋, <strong>{st.session_state['username']}</strong> Terima kasih telah menghubungi BPJS Ketenagakerjaan.
            Saat ini anda terhubungan dengan Iva (Information Virtual Assistances BPJS Ketenagakerjaan),
            apakah ada yang dapat saya bantu?
        </div>
        """,
        unsafe_allow_html=True,
    )

    for role, content in st.session_state.chat_history:
        if role == "user":
            st.chat_message("User").write(content)
        else:
            st.chat_message("Assistant").write(
                f"""
            <div style="text-align: justify;">
             {content}
            </div>
            """,
                unsafe_allow_html=True,
            )


# Fungsi reset input setelah respons asisten selesai
def reset_input(response_processed=True):
    st.session_state["response_in_progress"] = False
    st.session_state["response_processed"] = response_processed
    st.rerun()


def submited():
    st.session_state["response_in_progress"] = True
    st.session_state["popup_open"] = False


if not st.session_state["conversation_started"]:
    st.html(
        """
        <h1 style="text-align: center;">Selamat datang di IVA<Br>BPJS Ketenagakerjaan</h1>
        """,
    )
    st.markdown(
        """
        <p style="text-align: center;">😊 Sebelum kita ngobrol, isi data diri dulu ya, biar kita lebih akrab. Terima kasih! 🙏</p>
        """,
        unsafe_allow_html=True,
    )

    nik = st.text_input(
        "NIK",
        placeholder="Isi NIK Anda disini",
        max_chars=16,
    )
    name = st.text_input("Nama", placeholder="Isi Nama Anda disini")
    phone_number = st.text_input(
        "Nomor Telepon",
        placeholder="Isi Nomor Telepon Anda disini",
        max_chars=13,
    )
    # branch = st.selectbox("Pilih Cabang :", options)

    def is_valid_number(input_str):
        return input_str.isdigit()

    if st.button("Mulai Percakapan", use_container_width=True):
        # Validate if NIK and phone_number are numeric
        if not is_valid_number(nik):
            st.error("NIK harus berupa angka.")
        elif not is_valid_number(phone_number):
            st.error("Nomor telepon harus berupa angka.")
        # Validate NIK length
        elif len(nik) != 16:
            st.error("NIK harus berisi 16 digit.")
        # Validate phone number length
        elif len(phone_number) < 10 or len(phone_number) > 13:
            st.error("Nomor telepon harus berisi antara 10 hingga 13 digit.")
        # elif branch == '':
        #     st.error("Mohon pilih cabang terlebih dahulu.")
        elif name and phone_number:
            # Store session state if validation passes
            st.session_state["nik"] = nik
            st.session_state["username"] = name
            st.session_state["phone_number"] = phone_number
            st.session_state["conversation_started"] = True
            # st.session_state['branch'] = branch
            st.success(
                f"Terima kasih, {name}. Data Anda sudah disimpan. Anda dapat memulai percakapan."
            )
            time.sleep(1)
            st.rerun()
        else:
            st.error("Harap lengkapi semua kolom sebelum melanjutkan.")

else:
    chat_interface()

    prompt = st.chat_input(
        "Masukkan pesan Anda disini...",
        disabled=st.session_state["response_in_progress"],
        on_submit=submited,
    )

    if st.session_state["response_in_progress"]:
        if prompt:
            if is_spam(prompt):
                st.warning(
                    "Pesan Anda ditandai sebagai spam / kata-kata sensitif dan tidak dikirim. Mohon diperbaiki.",
                    icon="⚠️",
                )
                time.sleep(2)
                reset_input(response_processed=False)
                st.rerun()
            else:

                st.session_state.chat_history.append(("user", prompt))

                st.session_state.text_boxes.append(st.empty())
                st.session_state.text_boxes[-1].success(f" {prompt}")

                try:
                    client.beta.threads.messages.create(
                        thread_id=st.session_state.thread_id,
                        role="user",
                        content=prompt,
                    )

                    with client.beta.threads.runs.stream(
                        thread_id=st.session_state.thread_id,
                        assistant_id=assistant.id,
                        event_handler=EventHandler(),
                        temperature=1,
                    ) as stream:
                        stream.until_done()

                    reset_input()

                except Exception as e:
                    st.error(f"Error during response generation: {e}")
                    reset_input()
