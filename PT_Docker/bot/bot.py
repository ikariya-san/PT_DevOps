import logging
import re
import paramiko
import traceback

from telegram import ReplyKeyboardMarkup, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
import os
import subprocess
import psycopg2
from dotenv import load_dotenv
load_dotenv()

REPL_LOG_FILE = '/var/log/postgresql/postgresql-13-main.log'

TOKEN = os.getenv("TOKEN")

SSH_HOST = os.getenv("RM_HOST")
SSH_PORT = int(os.getenv("RM_PORT"))
SSH_USERNAME = os.getenv("RM_USER")
SSH_PASSWORD = os.getenv("RM_PASSWORD")
DB_NAME = os.getenv("DB_DATABASE")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))

FIND_PHONE_NUMBERS, CONFIRM_PHONE_NUMBERS = range(2)
FIND_EMAIL, CONFIRM_EMAIL = range(2)

# Подключаем логирование
logging.basicConfig(
    filename='logfile.txt', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)


# Функция для установки SSH-подключения
def ssh_connect():
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(hostname=SSH_HOST, port=SSH_PORT, username=SSH_USERNAME, password=SSH_PASSWORD)
    return ssh_client

def execute_ssh_command(host, port, username, password, command):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=host, port=port, username=username, password=password)
        stdin, stdout, stderr = ssh.exec_command(command)
        result = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        ssh.close()
        if error:
            return "Error: " + error
        return result if result else "Command executed, but no output returned."
    except Exception as e:
        return f"SSH command execution failed: {str(e)}"

def get_repl_logs(update: Update, context):
    query = update.message.text.split()
    if len(query) < 2:
        update.message.reply_text("Please specify a filter keyword from 'start', 'stop', 'ready'. For example: /get_repl_logs start")
        return

    filter_keyword = query[1].lower()
    # Настройка ключевых слов для grep в зависимости от запрашиваемой информации
    if filter_keyword == 'start':
        grep_keyword = "START_REPLICATION"  # Пример ключевого слова для запуска
    elif filter_keyword == 'stop':
        grep_keyword = "stop"  # Пример ключевого слова для остановки
    elif filter_keyword == 'ready':
        grep_keyword = "database system is ready to accept connections"  # Пример ключевого слова для готовност
    else:
        update.message.reply_text("Invalid filter keyword. Use 'start', 'stop', or 'ready'.")
        return

    command = f"docker logs pt_docker-db_repl-1 | grep '{grep_keyword}' | head -n 10"
    result = execute_ssh_command(SSH_HOST, SSH_PORT, SSH_USERNAME, SSH_PASSWORD, command)
    if result:
        update.message.reply_text(f"PostgreSQL Replication Logs for '{filter_keyword}':\n{result}")
    else:
        update.message.reply_text("No relevant logs found or access denied.")

def connect_to_db():
    try:
        conn = psycopg2.connect(
            dbname = DB_NAME,
            user = DB_USER,
            password = DB_PASSWORD,
            host = DB_HOST,
            port = DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        print("Error connecting to PostgreSQL database:", e)



def get_emails(update: Update, context):
    try:
        conn = connect_to_db()
        cur = conn.cursor()
        cur.execute("SELECT email FROM email_addresses;")
        emails = cur.fetchall()
        cur.close()
        conn.close()
        if emails:
            email_list = '\n'.join([email[0] for email in emails])
            update.message.reply_text(f"Email-адреса:\n{email_list}")
        else:
            update.message.reply_text("В базе данных нет email-адресов.")
    except Exception as e:
        print("Error fetching email addresses:", e)
        traceback.print_exc()  # Добавляем эту строку для вывода трассировки стека в случае ошибки
        update.message.reply_text("Произошла ошибка при получении email-адресов.")


def get_phone_numbers(update: Update, context):
    try:
        conn = connect_to_db()
        cur = conn.cursor()
        cur.execute("SELECT phone_number FROM phone_numbers;")
        phone_numbers = cur.fetchall()
        cur.close()
        conn.close()
        if phone_numbers:
            phone_number_list = '\n'.join([phone[0] for phone in phone_numbers])
            update.message.reply_text(f"Номера телефонов:\n{phone_number_list}")
        else:
            update.message.reply_text("В базе данных нет номеров телефонов.")
    except Exception as e:
        print("Error fetching phone numbers:", e)
        update.message.reply_text("Произошла ошибка при получении номеров телефонов.")




def start(update: Update, context):
    user = update.effective_user
    update.message.reply_text(f'Привет, {user.full_name}!')


def help_command(update: Update, context):
    update.message.reply_text('Помощь!')


def save_emails_to_db(emails):
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        for email in emails:
            cur.execute("INSERT INTO email_addresses (email) VALUES (%s)", (email,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        print("Error saving emails to database:", e)
        return False
    
def save_phone_numbers_to_db(phone_numbers):
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        for phone_number in phone_numbers:
            cur.execute("INSERT INTO phone_numbers (phone_number) VALUES (%s)", (phone_number,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        print("Error saving phone numbers to database:", e)
        return False

def find_phone_numbers_command(update, context):
    update.message.reply_text('Введите текст для поиска телефонных номеров: ')
    return FIND_PHONE_NUMBERS

def find_phone_numbers(update, context):
    user_input = update.message.text
    phone_pattern = re.compile(
        r'(?:\+7|8)\s?(?:\(\d{3}\)|\d{3})[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b'
    )
    phone_number_list = phone_pattern.findall(user_input)

    if not phone_number_list:
        update.message.reply_text('Телефонные номера не найдены')
        return ConversationHandler.END
    else:
        context.user_data['phone_numbers'] = phone_number_list
        phone_numbers = '\n'.join(phone_number_list)
        update.message.reply_text(f'Найденные телефонные номера:\n{phone_numbers}')

        keyboard = [
            [
                InlineKeyboardButton("Записать в базу данных", callback_data='write_to_db'),
                InlineKeyboardButton("Прекратить", callback_data='cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Выберите действие:', reply_markup=reply_markup)

        return CONFIRM_PHONE_NUMBERS

# Обработчик для кнопок
def button(update, context):
    query = update.callback_query
    query.answer()

    if query.data == 'write_to_db':
        if save_phone_numbers_to_db(context.user_data['phone_numbers']):
            query.edit_message_text('Номера телефонов успешно записаны в базу данных.')
        else:
            query.edit_message_text('Ошибка при записи номеров телефонов в базу данных.')
    elif query.data == 'cancel':
        query.edit_message_text('Взаимодействие завершено.')

    return ConversationHandler.END


def find_email_command(update, context):
    update.message.reply_text('Введите текст для поиска email-адресов:')
    return FIND_EMAIL

def find_email(update, context):
    user_input = update.message.text

    # Регулярное выражение для поиска email-адресов
    email_regex = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')

    email_list = email_regex.findall(user_input)

    if not email_list:
        update.message.reply_text('Email-адреса не найдены')
        return ConversationHandler.END
    else:
        context.user_data['emails'] = email_list
        emails = '\n'.join(email_list)
        update.message.reply_text(f'Найденные email-адреса:\n{emails}')

        keyboard = [
            [
                InlineKeyboardButton("Записать в базу данных", callback_data='write_email_to_db'),
                InlineKeyboardButton("Прекратить", callback_data='cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Выберите действие:', reply_markup=reply_markup)

        return CONFIRM_EMAIL

def button2(update, context):
    query = update.callback_query
    query.answer()

    if query.data == 'write_email_to_db':
        if save_emails_to_db(context.user_data['emails']):
            query.edit_message_text('Email-адреса успешно записаны в базу данных.')
        else:
            query.edit_message_text('Ошибка при записи email-адресов в базу данных.')
    elif query.data == 'cancel':
        query.edit_message_text('Взаимодействие завершено.')

    return ConversationHandler.END

# Функция для проверки сложности пароля
def verify_password_command(update: Update, context):
    update.message.reply_text('Введите пароль: ')
    return 'verify_password'


def verify_password(update: Update, context):
    password = update.message.text

    # Регулярное выражение для проверки сложности пароля
    password_regex = re.compile(
        r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*()])[A-Za-z\d!@#$%^&*()]{8,}$'
    )

    if password_regex.match(password):
        update.message.reply_text('Пароль сложный')
    else:
        update.message.reply_text('Пароль простой')

    return ConversationHandler.END

def get_release(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("lsb_release -a")
    release_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(release_info)


def get_uname(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("uname -a")
    uname_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(uname_info)


def get_uptime(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("uptime")
    uptime_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(uptime_info)


def get_df(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("df -h")
    df_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(df_info)


def get_free(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("free -m")
    free_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(free_info)


def get_mpstat(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("mpstat")
    mpstat_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(mpstat_info)


def get_w(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("w")
    w_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(w_info)


def get_auths(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("last -10")
    auths_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(auths_info)


def get_critical(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("tail -5 /var/log/syslog")
    critical_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(critical_info)


def get_ps(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("ps aux | head -n 10")
    ps_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(ps_info)


def get_ss(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("ss -tuln")
    ss_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(ss_info)

def get_apt_list(update: Update, context):
    update.message.reply_text("Enter a package name to search for, or type 'all' to list all packages.")
    return 'get_apt_list'

def handle_apt_package(update: Update, context):
    package_name = update.message.text
    if package_name.lower() == 'all':
        command = 'dpkg -l | head -n 10'
    else:
        command = f'dpkg -l | grep {package_name} | head -n 10'
    result = execute_ssh_command(SSH_HOST, SSH_PORT, SSH_USERNAME, SSH_PASSWORD, command)
    update.message.reply_text(f"Package Information:\n{result}")
    return ConversationHandler.END

def get_services(update: Update, context):
    ssh_client = ssh_connect()
    stdin, stdout, stderr = ssh_client.exec_command("service --status-all")
    services_info = stdout.read().decode('utf-8')
    ssh_client.close()
    update.message.reply_text(services_info)


def echo(update: Update, context):
    update.message.reply_text(update.message.text)


def main():
    updater = Updater(TOKEN, use_context=True)

    # Получаем диспетчер для регистрации обработчиков
    dp = updater.dispatcher

    conv_handler_find_phone_numbers = ConversationHandler(
    entry_points=[CommandHandler('find_phone_numbers', find_phone_numbers_command)],
    states={
        FIND_PHONE_NUMBERS: [MessageHandler(Filters.text & ~Filters.command, find_phone_numbers)],
        CONFIRM_PHONE_NUMBERS: [CallbackQueryHandler(button)]
    },
    fallbacks=[]
)


    conv_handler_find_email = ConversationHandler(
    entry_points=[CommandHandler('find_email', find_email_command)],
    states={
        FIND_EMAIL: [MessageHandler(Filters.text & ~Filters.command, find_email)],
        CONFIRM_EMAIL: [CallbackQueryHandler(button2)]
    },
    fallbacks=[]
)

    conv_handler_verify_password = ConversationHandler(
    entry_points=[CommandHandler('verify_password', verify_password_command)],
    states={'verify_password': [MessageHandler(Filters.text & ~Filters.command, verify_password)]},
    fallbacks=[]
    )

    convHandlerAptList = ConversationHandler(
        entry_points=[CommandHandler('get_apt_list', get_apt_list)],
        states={
            'get_apt_list': [MessageHandler(Filters.text & ~Filters.command, handle_apt_package)],
        },
        fallbacks=[]
    )
    

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(conv_handler_find_phone_numbers)
    dp.add_handler(conv_handler_find_email)
    dp.add_handler(conv_handler_verify_password)
    dp.add_handler(CommandHandler("get_repl_logs", get_repl_logs))
    dp.add_handler(CommandHandler("get_emails", get_emails))
    dp.add_handler(CommandHandler("get_phone_numbers", get_phone_numbers))

    
    # Регистрируем обработчики команд

    dp.add_handler(CommandHandler("get_release", get_release))
    dp.add_handler(CommandHandler("get_uname", get_uname))
    dp.add_handler(CommandHandler("get_uptime", get_uptime))
    dp.add_handler(CommandHandler("get_df", get_df))
    dp.add_handler(CommandHandler("get_free", get_free))
    dp.add_handler(CommandHandler("get_mpstat", get_mpstat))
    dp.add_handler(CommandHandler("get_w", get_w))
    dp.add_handler(CommandHandler("get_auths", get_auths))
    dp.add_handler(CommandHandler("get_critical", get_critical))
    dp.add_handler(CommandHandler("get_ps", get_ps))
    dp.add_handler(CommandHandler("get_ss", get_ss))
    dp.add_handler(convHandlerAptList)
    dp.add_handler(CommandHandler("get_services", get_services))

    # Регистрируем обработчик текстовых сообщений
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    # Запускаем бота
    updater.start_polling()

    # Останавливаем бота при нажатии Ctrl+C
    updater.idle()


if __name__ == '__main__':
    main()
