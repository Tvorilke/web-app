import rusenttokenize.ru_sent_tokenize as rst
import os
import spacy
import sqlite3
import re

nlp = spacy.load('ru_core_news_sm')


def main():
    try:
        sqlite_connection = sqlite3.connect('./web_app/web_app.db')
        cursor = sqlite_connection.cursor()
        get_files(cursor)
        sqlite_connection.commit()
        cursor.close()
    except sqlite3.Error as error:
        print("Ошибка при подключении к sqlite", error)
    finally:
        if sqlite_connection:
            sqlite_connection.close()


def get_files(c):
    for fldr in os.listdir('../texts/'):
        try:
            for file in os.listdir('./texts/' + fldr + '/'):
                if file.endswith('.txt') and not file.startswith('meta-'):
                    sentences = []
                    with open('./texts/' + fldr + '/' + file, 'r') as text_file:
                        for line in text_file.readlines():
                            sentences.extend(sent_tokenize(line))
                    for sent in sentences:
                        markup(sent, fldr, file, c)
        except NotADirectoryError:
            pass


def sent_tokenize(text):
    sentences = rst(text)
    sentences = [s for s in sentences if s != '']
    '''merge = lambda s: reduce(operator.iadd, s, [])
    sentences = merge(sentences)'''
    return sentences


def markup(sent_text, text_theme='', file_name='', c=()):
    sent_markup = []
    sent_text = re.sub(r' *\[[\d\D]+\]*', '', sent_text)  # удаляет ссылку на источник
    if sent_text.count('"') % 2 != 0:  # удалляет одинокие кавычки
        sent_text = sent_text.replace('"', '')
    if sent_text.count('«') != sent_text.count('»'):
        sent_text = sent_text.replace('«', '')
        sent_text = sent_text.replace('»', '')
    if sent_text.count('(') != sent_text.count(')'):
        sent_text = sent_text.replace('(', '')
        sent_text = sent_text.replace(')', '')
    if sent_text.count('[') != sent_text.count(']'):
        sent_text = sent_text.replace('[', '')
        sent_text = sent_text.replace(']', '')
    doc = nlp(sent_text)
    for token in doc:
        sent_markup.append('(' + token.text + ', ' + token.pos_ + ', ' + token.dep_ + ', ' +
                           token.head.text + ', ' + str(token.idx) + ', ' + str(token.idx + len(token.text))
                           + ', ' + ', '.join([_.text for _ in token.children]) + ')')
    sent_markup = '; '.join(sent_markup)
    if file_name:
        add_to_db(sent_text, sent_markup, file_name, text_theme, c)
    else:
        return sent_markup


def add_to_db(sent_text, sent_markup, file_name, text_theme, cursor):
    data = (sent_text, sent_markup, text_theme, file_name)
    try:
        sqlite_insert_query = """INSERT INTO sentences_markup
                                (sent_text, sent_markup, text_theme, file_name) VALUES(?, ?, ?, ?);"""
        cursor.execute(sqlite_insert_query, data)
    except sqlite3.Error as error:
        print("Не удалось вставить данные в таблицу sentences_markup")
        print("Класс исключения: ", error.__class__)
        print("Исключение", error.args)


if __name__ == '__main__':
    main()
    print('Done!')
