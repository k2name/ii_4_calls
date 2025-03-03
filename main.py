import os
import sqlite3
import openai
from pydub import AudioSegment
import configparser

# Чтение конфиг-файла
def read_config():
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config['DEFAULT']['OpenAI_API_Key']

# Настройки OpenAI API
openai.api_key = read_config()

# Настройки базы данных
DB_NAME = "call_center.db"

# Создание базы данных и таблиц
def create_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Таблица для хранения звонков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT NOT NULL,
            call_date TEXT NOT NULL,
            transcript TEXT NOT NULL,
            friendliness_score REAL,
            respect_score REAL,
            script_following_score REAL
        )
    ''')

    conn.commit()
    conn.close()

# Функция для чтения скрипта из файла
def read_script(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

# Функция для распознавания речи из MP3-файла
def transcribe_audio(file_path):
    try:
        # Конвертируем MP3 в WAV (Whisper работает с WAV)
        audio = AudioSegment.from_mp3(file_path)
        wav_path = file_path.replace(".mp3", ".wav")
        audio.export(wav_path, format="wav")

        # Отправляем аудио в OpenAI Whisper для распознавания
        with open(wav_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)

        # Удаляем временный WAV-файл
        os.remove(wav_path)

        return transcript["text"]
    except Exception as e:
        print(f"Ошибка при распознавании аудио: {e}")
        return None

# Функция для анализа текста и оценки звонка
def analyze_call(transcript, script):
    try:
        # Запрос к GPT-4 для анализа текста
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": f"Ты анализируешь диалог сотрудника колл-центра и клиента. Оцени дружелюбность, уважительность и следование скрипту общения сотрудника. Скрипт для общения:\n\n{script}"},
                {"role": "user", "content": f"Проанализируй следующий диалог и оцени его:\n\n{transcript}"}
            ]
        )

        # Извлекаем оценку из ответа GPT-4
        analysis = response["choices"][0]["message"]["content"]
        return analysis
    except Exception as e:
        print(f"Ошибка при анализе текста: {e}")
        return None

# Функция для сохранения данных в базу данных
def save_call_to_db(employee_name, call_date, transcript, analysis):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Извлекаем оценки из анализа (пример: GPT-4 возвращает текстовый анализ)
    friendliness_score = 0.0
    respect_score = 0.0
    script_following_score = 0.0

    # Пример парсинга анализа (зависит от формата ответа GPT-4)
    if "дружелюбность" in analysis:
        friendliness_score = float(analysis.split("дружелюбность: ")[1].split("/")[0])
    if "уважительность" in analysis:
        respect_score = float(analysis.split("уважительность: ")[1].split("/")[0])
    if "следование скрипту" in analysis:
        script_following_score = float(analysis.split("следование скрипту: ")[1].split("/")[0])

    # Сохраняем данные в базу
    cursor.execute('''
        INSERT INTO calls (employee_name, call_date, transcript, friendliness_score, respect_score, script_following_score)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (employee_name, call_date, transcript, friendliness_score, respect_score, script_following_score))

    conn.commit()
    conn.close()

# Функция для генерации отчета по сотруднику
def generate_report(employee_name, start_date, end_date):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Получаем данные о звонках за указанный период
    cursor.execute('''
        SELECT COUNT(*) as total_calls,
               AVG(friendliness_score) as avg_friendliness,
               AVG(respect_score) as avg_respect,
               AVG(script_following_score) as avg_script_following
        FROM calls
        WHERE employee_name = ? AND call_date BETWEEN ? AND ?
    ''', (employee_name, start_date, end_date))

    result = cursor.fetchone()

    if result:
        print(f"Отчет по сотруднику {employee_name} за период с {start_date} по {end_date}:")
        print(f"Всего звонков: {result[0]}")
        print(f"Средняя оценка дружелюбности: {result[1]:.2f}")
        print(f"Средняя оценка уважительности: {result[2]:.2f}")
        print(f"Средняя оценка следования скрипту: {result[3]:.2f}")
    else:
        print("Данные не найдены.")

    conn.close()

# Основная функция программы
def main():
    # Создаем базу данных
    create_database()

    # Директория с MP3-файлами
    mp3_directory = "path_to_mp3_files"  # Укажите путь к директории с MP3-файлами

    # Чтение скрипта из файла
    script_path = "script.txt"  # Укажите путь к файлу со скриптом
    script = read_script(script_path)

    # Сканируем директорию
    for filename in os.listdir(mp3_directory):
        if filename.endswith(".mp3"):
            file_path = os.path.join(mp3_directory, filename)
            print(f"Обработка файла: {filename}")

            # Распознаем аудио
            transcript = transcribe_audio(file_path)
            if transcript:
                print("Текст распознан.")

                # Анализируем текст
                analysis = analyze_call(transcript, script)
                if analysis:
                    print("Анализ завершен.")

                    # Сохраняем данные в базу
                    employee_name = filename.split("_")[0]  # Пример: имя сотрудника из имени файла
                    call_date = "2023-10-01"  # Пример: дата звонка
                    save_call_to_db(employee_name, call_date, transcript, analysis)

    # Генерация отчета
    generate_report("Иван Иванов", "2023-10-01", "2023-10-31")

if __name__ == "__main__":
    main()