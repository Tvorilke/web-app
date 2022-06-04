import pymorphy3
#import enchant
import sqlite3
import traceback
import sys
morph = pymorphy3.MorphAnalyzer()
#d = enchant.Dict("ru")


def get_rows():
    try:
        sqlite_connection = sqlite3.connect('../DB/web_app.db')
        cursor = sqlite_connection.cursor()
        sqlite_select_query = """SELECT * from sentences_markup"""
        cursor.execute(sqlite_select_query)
        records = cursor.fetchall()
        print("Всего строк:  ", len(records))
        for row in records:
            sent_id = row[0]  # 2
            sent_text = row[1]  # Формирование тематики исследования для молодого ученого всегда является трудоемкой
            # задачей.
            sent_markup = row[2]  # (Формирование, NOUN, nsubj, является, [тематики], 0, 12); (тематики, NOUN, nmod,
            # Формирование, [исследования], 13, 21); (исследования, NOUN, nmod, тематики, [ученого], 22, 34); (для,
            # ADP, case, ученого, [], 35, 38); (молодого, ADJ, amod, ученого, [], 39, 47); (ученого, NOUN, nmod,
            # исследования, [для, молодого], 48, 55); (всегда, ADV, advmod, является, [], 56, 62); (является, VERB,
            # ROOT, является, [Формирование, всегда, задачей, .], 63, 71); (трудоемкой, ADJ, amod, задачей, [], 72,
            # 82); (задачей, NOUN, xcomp, является, [трудоемкой], 83, 90); (., PUNCT, punct, является, [], 90, 91)
            text_theme = row[3]
            data = task_pssv_gen(sent_text, sent_markup, sent_id, text_theme)
            if data:
                try:
                    sqlite_insert_query = """INSERT INTO exercises
                                    (type, exer_text, words_to_mod, answer, hint, sent_id, text_theme) VALUES(?, ?, ?, ?, ?, ?, ?);"""
                    cursor.execute(sqlite_insert_query, data)
                except sqlite3.Error as error:
                    print("Не удалось вставить данные в таблицу sentences_markup")
                    print("Класс исключения: ", error.__class__)
                    print("Исключение", error.args)
                    print("Печать подробноcтей исключения SQLite: ")
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    print(traceback.format_exception(exc_type, exc_value, exc_tb))
        sqlite_connection.commit()
        cursor.close()
    except sqlite3.Error as error:
        print("Ошибка при работе с SQLite", error)
    finally:
        if sqlite_connection:
            sqlite_connection.close()


def task_pssv_gen(sent_text, sent_markup, sent_id, text_theme=''):
    if 2 < len(sent_text.split(' ')) < 31 and sent_text[0].isupper():  # отсекает слишком короткие / длинные
        # предложения и проверяет, что первая буква заглавная (то есть взято предложение с начала)
        verb, words_to_mod, subj, aux_text = '', '', '', ''
        aux = []
        sent_markup = sent_markup[1:-1]
        sent_markup = sent_markup.split('); (')
        sent_markup = [_.split(', ', maxsplit=6) for _ in sent_markup]  # token.text, token.pos_, token.dep_,
        # token.head.text, token.idx, token.idx + len(token.text), token.children
        for word in sent_markup:  # [Формирование, NOUN, nsubj, является, 0, 12, [тематики]]
            if word[0].isalpha:  # d.check(word[0]) # исключает иностранные слова и слова с орфографическими ошибками
                if word[2] == "ROOT" and word[1] == 'VERB' and not verb and morph.parse(word[0])[0].tag.voice == 'pssv':
                    # поиск сказуемого
                    verb = word
                    children_v = [_ for _ in sent_markup if _[0] in verb[6].split(', ')]  # список токенов, зависимых
                    # от глагола (I уровень)
                    for ch_v in children_v:
                        #if d.check(ch_v[0]):
                        if ch_v[2] in ["nsubj", "nsubj:pass"] and ch_v[1] in ['NOUN', 'PRON'] \
                                and not subj and morph.parse(ch_v[0])[0].tag.case == 'nomn':  # поиск подлежащего
                            subj = ch_v
                if word[2] == "aux:pass":
                    aux.append(word)
        if not subj or not verb:
            return
        if morph.parse(subj[0])[0].tag.number != morph.parse(verb[0])[0].tag.number:
            return
        if morph.parse(verb[0])[0].tag.tense == 'past' and morph.parse(verb[0])[0].tag.number == 'sing':
            if morph.parse(subj[0])[0].tag.gender != morph.parse(verb[0])[0].tag.gender and \
                    morph.parse(subj[0])[0].tag.gender:
                return
        if subj[1] == "PRON":
            if morph.parse(subj[0])[0].tag.person != morph.parse(verb[0])[0].tag.person and \
                    morph.parse(verb[0])[0].tag.person:
                return
        else:

            for _ in aux:  # всмогательный глагол для сказуемого
                if _[3] == verb:
                    aux_text = _[0]
            exer_text = sent_text
            tokens_to_replace = [aux_text, verb]
            tokens_to_replace = [_ for _ in tokens_to_replace if _]
            tokens_to_replace.sort(key=lambda k: int(k[4]))
            for _ in tokens_to_replace:
                exer_text = exer_text[:int(verb[4])] + '_' * len(verb[0]) + exer_text[int(verb[5]):]
            exer_text = exer_text[:int(subj[4])] + '<b>' + subj[0] + '</b>' + exer_text[int(subj[5]):]
            words_to_mod = ' '.join([morph.parse(_[0])[0].normal_form.upper() for _ in tokens_to_replace])
            answer = verb[0]
            hint = ''
            tense = {'past': 'прошедшее', 'pres': 'настоящее', 'futr': 'будущее'}
            gender = {'masc': 'мужской', 'femn': 'женский', 'neut': 'средний'}
            number = {'sing': 'единственное', 'plur': 'множественное'}
            if morph.parse(verb[0])[0].tag.tense:
                hint += 'время: ' + tense[morph.parse(verb[0])[0].tag.tense] + '\n'
            if morph.parse(verb[0])[0].tag.number:
                hint += 'число: ' + number[morph.parse(verb[0])[0].tag.number] + '\n'
            if morph.parse(verb[0])[0].tag.gender:
                hint += 'род: ' + gender[morph.parse(verb[0])[0].tag.gender]
            data = ('pssv', exer_text, words_to_mod, answer, hint, int(sent_id), text_theme)
            return data


if __name__ == '__main__':
    get_rows()
    print('Done!')
