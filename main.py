#!/usr/bin/python

import pandas as pd
import jaydebeapi
import glob
import shutil
import os
conn = jaydebeapi.connect(
    'oracle.jdbc.driver.OracleDriver',
    'jdbc:oracle:thin:de2tm/balinfundinson@de-oracle.chronosavant.ru:1521/deoracle',
   # pasword ...,
    '../ojdbc8.jar'
)
curs = conn.cursor()
conn.jconn.setAutoCommit(False)
# очистка стг
curs.execute("delete from HLOV_STG_PASSPORT_BLACKLIST")
curs.execute("delete from HLOV_STG_TRANSACTIONS")
curs.execute("delete from HLOV_STG_TERMINAL")
curs.execute("delete from HLOV_STG_CARDS")
curs.execute("delete from HLOV_STG_ACCOUNTS")
curs.execute("delete from HLOV_STG_CLIENTS")
curs.execute("delete from HLOV_STG_DELETE_TERMINAL")
curs.execute("delete from HLOV_STG_DELETE_CARDS")
curs.execute("delete from HLOV_STG_DELETE_ACCOUNTS")
curs.execute("delete from HLOV_STG_DELETE_CLIENTS")
# путь к файлам
file_pb = glob.glob('/home/de2tm/HLOV/passport_blacklist*.xlsx')
file_ter = glob.glob('/home/de2tm/HLOV/terminals*.xlsx')
file_tr = glob.glob('/home/de2tm/HLOV/transactions*.csv')
# чтение из файлов
passport_blacklist_df = pd.read_excel(file_pb[0])
terminals_df = pd.read_excel(file_ter[0])
transactions_df = pd.read_csv(file_tr[0], sep=';', decimal=",")
# выборка новых записей из passport_blacklist_df
curs.execute("select LAST_UPDATE_DT from HLOV_META_PASSPORT_BLACKLIST")
last_dt_pbl = curs.fetchall()
passport_blacklist_df = passport_blacklist_df.loc[passport_blacklist_df['date'] > last_dt_pbl[0][0]]
# преобразование дат
transactions_df['transaction_date'] = transactions_df['transaction_date'].astype(str)
passport_blacklist_df['date'] = passport_blacklist_df['date'].astype(str)
# загрузка в стг
if passport_blacklist_df.empty is False:
    curs.executemany("""insert into HLOV_STG_PASSPORT_BLACKLIST
                    (ENTRY_DT, PASSPORT_NUM)
                    values (to_date(?, 'YYYY-MM-DD'), ?)""",
                     passport_blacklist_df.values.tolist())
if transactions_df.empty is False:
    curs.executemany("""insert into HLOV_STG_TRANSACTIONS
                    (TRANS_ID, TRANS_DATE, AMT, CARD_NUM, OPER_TYPE, OPER_RESULT, TERMINAL)
                    values (?, to_date(?, 'YYYY-MM-DD HH24:MI:SS'), ?, ?, ?, ?, ?)""",
                     transactions_df.values.tolist())
if terminals_df.empty is False:
    curs.executemany("""insert into HLOV_STG_TERMINAL 
                 (TERMINAL_ID, TERMINAL_TYPE, TERMINAL_CITY, TERMINAL_ADDRESS)
                 values (?, ?, ?, ?)""", terminals_df.values.tolist())
curs.execute(""" select count(*)
                from BANK.ACCOUNTS
                where coalesce(UPDATE_DT,CREATE_DT) > (
                select LAST_UPDATE_DT from HLOV_META_ACCOUNTS)""")
count_account = curs.fetchone()[0]
if count_account > 0:
    curs.executemany("""insert into HLOV_STG_ACCOUNTS 
                    (ACCOUNT_NUM, VALID_TO, CLIENT, CREATE_DT, UPDATE_DT)
                    select 
                    ACCOUNT, VALID_TO, CLIENT, CREATE_DT, UPDATE_DT 
                    from BANK.ACCOUNTS
                    where coalesce(UPDATE_DT,CREATE_DT) > (
                    select LAST_UPDATE_DT from HLOV_META_ACCOUNTS)""")
curs.execute("""select count(*)
                from BANK.CARDS
                where coalesce(UPDATE_DT,CREATE_DT) > (
                select LAST_UPDATE_DT from HLOV_META_CARDS)""")
count_cards = curs.fetchone()[0]
if count_cards > 0:
    curs.executemany("""insert into HLOV_STG_CARDS
                    (CARD_NUM , ACCOUNT, CREATE_DT, UPDATE_DT)
                    select CARD_NUM , ACCOUNT, CREATE_DT, UPDATE_DT
                    from BANK.CARDS
                    where coalesce(UPDATE_DT,CREATE_DT) > (
                    select LAST_UPDATE_DT from HLOV_META_CARDS)""")

curs.execute("""select count(*)
                from BANK.CLIENTS
                where coalesce(UPDATE_DT,CREATE_DT) > (
                select LAST_UPDATE_DT from HLOV_META_CLIENTS)""")
count_clients = curs.fetchone()[0]
if count_clients > 0:
    curs.executemany("""insert into HLOV_STG_CLIENTS
                    (CLIENT_ID, LAST_NAME, FIRST_NAME, PATRONYMIC, DATE_OF_BIRTH, 
                    PASSPORT_NUM, PASSPORT_VALID_TO, PHONE, CREATE_DT, UPDATE_DT)
                    select CLIENT_ID, LAST_NAME, FIRST_NAME, PATRONYMIC, DATE_OF_BIRTH, 
                    PASSPORT_NUM, PASSPORT_VALID_TO, PHONE, CREATE_DT, UPDATE_DT
                    from BANK.CLIENTS
                    where coalesce(UPDATE_DT,CREATE_DT) > (
                    select LAST_UPDATE_DT from HLOV_META_CLIENTS)""")
# создание переменной даты
curs.execute("select trans_date from HLOV_STG_TRANSACTIONS")
current_date = curs.fetchone()[0]
print(current_date)
curs.execute("select trans_date - interval '1' day from HLOV_STG_TRANSACTIONS")
prev_current_date = curs.fetchone()[0]
# загрузка в приемник
curs.execute("select count(*) from HLOV_STG_PASSPORT_BLACKLIST")
count_stg_pass = curs.fetchone()[0]
if count_stg_pass > 0:
    curs.execute("""insert into HLOV_DWH_FACT_PSSPRT_BLCKLST(PASSPORT_NUM, ENTRY_DT)
                    select
                        PASSPORT_NUM,
                        ENTRY_DT
                    from HLOV_STG_PASSPORT_BLACKLIST""")
curs.execute("select count(*) from HLOV_STG_TRANSACTIONS")
count_stg_trans = curs.fetchone()[0]
if count_stg_trans > 0:
    curs.execute("""insert into HLOV_DWH_FACT_TRANSACTIONS(TRANS_ID, TRANS_DATE, CARD_NUM, OPER_TYPE,AMT, OPER_RESULT, TERMINAL)
                       select
                            TRANS_ID, TRANS_DATE, CARD_NUM, OPER_TYPE,
                            AMT, OPER_RESULT, TERMINAL
                        from HLOV_STG_TRANSACTIONS""")
ins = """insert into HLOV_DWH_DIM_TERMINAL_HIST (TERMINAL_ID, TERMINAL_TYPE, TERMINAL_CITY, 
                TERMINAL_ADDRESS, EFFECTIVE_FROM)
                select stg.TERMINAL_ID, stg.TERMINAL_TYPE, stg.TERMINAL_CITY, stg.TERMINAL_ADDRESS, to_date('{}', 'YYYY-MM-DD HH24:MI:SS')
                from HLOV_DWH_DIM_TERMINAL_HIST dwh
                full join HLOV_STG_TERMINAL stg
                on dwh.terminal_id = stg.terminal_id
                where dwh.terminal_id is null""".format(current_date)
curs.execute(ins)
curs.execute("select count(*) from HLOV_STG_ACCOUNTS")
count_stg_acc = curs.fetchone()[0]
if count_stg_acc > 0:
    curs.executemany(""" insert into HLOV_DWH_DIM_ACCOUNTS_HIST( ACCOUNT_NUM, VALID_TO, CLIENT, EFFECTIVE_FROM)
                    select
                        ACCOUNT_NUM,
                        VALID_TO,
                        CLIENT,
                        coalesce(UPDATE_DT,CREATE_DT)
                    from HLOV_STG_ACCOUNTS""")
curs.execute("select count(*) from HLOV_STG_ACCOUNTS")
count_stg_acc = curs.fetchone()[0]
if count_stg_acc > 0:
    curs.executemany(""" merge into HLOV_DWH_DIM_ACCOUNTS_HIST dwh
                        using HLOV_STG_ACCOUNTS stg
                        on (dwh.ACCOUNT_NUM = stg.ACCOUNT_NUM and dwh.EFFECTIVE_FROM < coalesce(stg.UPDATE_DT,stg.CREATE_DT))
                        when matched then update set 
                        dwh.EFFECTIVE_TO = coalesce(stg.UPDATE_DT,stg.CREATE_DT) - 1
                        where dwh.EFFECTIVE_TO = to_date('5999-12-01', 'YYYY-MM-DD')""")
curs.execute("select count(*) from HLOV_STG_CLIENTS")
count_stg_cl = curs.fetchone()[0]
if count_stg_cl > 0:
    curs.executemany("""insert into HLOV_DWH_DIM_CLIENTS_HIST(CLIENT_ID, LAST_NAME, FIRST_NAME, PATRONYMIC,DATE_OF_BIRTH, PASSPORT_NUM, PASSPORT_VALID_TO, PHONE, EFFECTIVE_FROM)
                    select
                        CLIENT_ID, LAST_NAME, FIRST_NAME, PATRONYMIC,
                        DATE_OF_BIRTH, PASSPORT_NUM, PASSPORT_VALID_TO, PHONE, coalesce(UPDATE_DT,CREATE_DT)
                    from HLOV_STG_CLIENTS""")
curs.execute("select count(*) from HLOV_STG_CLIENTS")
count_stg_cl = curs.fetchone()[0]
if count_stg_cl > 0:
    curs.executemany("""merge into HLOV_DWH_DIM_CLIENTS_HIST dwh
                        using HLOV_STG_CLIENTS stg
                        on (dwh.CLIENT_ID = stg.CLIENT_ID and dwh.EFFECTIVE_FROM < coalesce(stg.UPDATE_DT,stg.CREATE_DT))
                        when matched then update set
                        dwh.EFFECTIVE_TO = coalesce(stg.UPDATE_DT,stg.CREATE_DT) - 1
                        where dwh.EFFECTIVE_TO = to_date('5999-12-01', 'YYYY-MM-DD')""")
curs.execute("select count(*) from HLOV_STG_CARDS")
count_stg_car = curs.fetchone()[0]
if count_stg_car > 0:
    curs.executemany("""insert into HLOV_DWH_DIM_CARDS_HIST(CARD_NUM, ACCOUNT_NUM, EFFECTIVE_FROM)
                        select
                        CARD_NUM, ACCOUNT, coalesce(UPDATE_DT,CREATE_DT)
                        from HLOV_STG_CARDS""")
curs.execute("select count(*) from HLOV_STG_CARDS")
count_stg_car = curs.fetchone()[0]
if count_stg_car > 0:
    curs.executemany("""merge into HLOV_DWH_DIM_CARDS_HIST dwh
                        using HLOV_STG_CARDS stg
                        on (dwh.CARD_NUM = stg.CARD_NUM and dwh.EFFECTIVE_FROM < coalesce(stg.UPDATE_DT,stg.CREATE_DT))
                        when matched then update set 
                        dwh.EFFECTIVE_TO = coalesce(stg.UPDATE_DT,stg.CREATE_DT) - 1
                        where dwh.EFFECTIVE_TO = to_date('5999-12-01', 'YYYY-MM-DD')""")
# проверка удалений
curs.execute("""insert into HLOV_STG_DELETE_CARDS( CARD_NUM )
select CARD_NUM from BANK.CARDS""")
curs.execute("""insert into HLOV_STG_DELETE_ACCOUNTS( ACCOUNT_NUM )
select ACCOUNT_NUM from BANK.ACCOUNTS""")
curs.execute("""insert into HLOV_STG_DELETE_CLIENTS( CLIENT_ID )
select CLIENT_ID from BANK.CLIENTS""")
# вставка новой версии удалений
ins = """insert into HLOV_DWH_DIM_CARDS_HIST 
            (CARD_NUM, ACCOUNT_NUM, EFFECTIVE_FROM, DELETED_FLG)
            select
            dwh.CARD_NUM,
            dwh.ACCOUNT_NUM,
            '5999-12-01',
            1
            from HLOV_DWH_DIM_CARDS_HIST dwh
            left join
            HLOV_STG_DELETE_CARDS stg
            on dwh.CARD_NUM = stg.CARD_NUM
            where
            stg.CARD_NUM is null
            and dwh.EFFECTIVE_TO = to_date('5999-12-01','YYYY-MM-DD')
            and dwh.DELETED_FLG = '0' """.format(current_date)
curs.execute(ins)
ins = """insert into HLOV_DWH_DIM_ACCOUNTS_HIST (ACCOUNT_NUM, VALID_TO, CLIENT, 
            EFFECTIVE_FROM, DELETED_FLG)
            select
                dwh.ACCOUNT_NUM,
                dwh.VALID_TO,
                dwh.CLIENT,
                '5999-12-01',
                1
            from HLOV_DWH_DIM_ACCOUNTS_HIST dwh
            left join HLOV_STG_DELETE_ACCOUNTS stg
            on dwh.ACCOUNT_NUM = stg.ACCOUNT_NUM
            where stg.ACCOUNT_NUM is null
            and dwh.EFFECTIVE_TO = to_date('5999-12-01', 'YYYY-MM-DD')
            and dwh.DELETED_FLG = '0'""".format(current_date)
curs.execute(ins)
ins = """insert into HLOV_DWH_DIM_CLIENTS_HIST (CLIENT_ID, LAST_NAME, FIRST_NAME, PATRONYMIC, 
            DATE_OF_BIRTH, PASSPORT_NUM, PASSPORT_VALID_TO, 
            PHONE, EFFECTIVE_FROM, DELETED_FLG)
            select 
                dwh.CLIENT_ID,
                dwh.LAST_NAME,
                dwh.FIRST_NAME,
                dwh.PATRONYMIC,
                dwh.DATE_OF_BIRTH,
                dwh.PASSPORT_NUM,
                dwh.PASSPORT_VALID_TO,
                dwh.PHONE,
                '5999-12-01',
                1
                from HLOV_DWH_DIM_CLIENTS_HIST dwh
                left join HLOV_STG_DELETE_CLIENTS stg
                on dwh.CLIENT_ID = stg.CLIENT_ID
                where stg.CLIENT_ID is null
                and dwh.EFFECTIVE_TO = to_date('5999-12-01', 'YYYY-MM-DD')
                and dwh.DELETED_FLG = '0'""".format(current_date)
curs.execute(ins)
ins = """insert into HLOV_DWH_DIM_TERMINAL_HIST (TERMINAL_ID, TERMINAL_TYPE, TERMINAL_CITY, 
                TERMINAL_ADDRESS, EFFECTIVE_FROM,DELETED_FLG)
                select dwh.TERMINAL_ID,
                       dwh.TERMINAL_TYPE, 
                       dwh.TERMINAL_CITY, 
                       dwh.TERMINAL_ADDRESS, 
                      '5999-12-01',
                       1
                from HLOV_DWH_DIM_TERMINAL_HIST dwh
                full join HLOV_STG_TERMINAL stg
                on dwh.terminal_id = stg.terminal_id
                where stg.terminal_id is null
                and dwh.EFFECTIVE_TO = to_date('5999-12-01', 'YYYY-MM-DD')
                and dwh.DELETED_FLG = '0' """.format(current_date)
curs.execute(ins)
# закрытие старой версии удалений
ins = """update HLOV_DWH_DIM_CARDS_HIST
            set EFFECTIVE_TO = '5999-12-01' 
            where CARD_NUM in ( 
                        select
                        dwh.CARD_NUM
                        from HLOV_DWH_DIM_CARDS_HIST dwh
                        left join
                        HLOV_STG_DELETE_CARDS stg
                        on dwh.CARD_NUM = stg.CARD_NUM
                        where
                        stg.CARD_NUM is null
                        and dwh.EFFECTIVE_TO = to_date('5999-12-01','YYYY-MM-DD')
                        and dwh.DELETED_FLG = '0')""".format(prev_current_date)
curs.execute(ins)
ins = """update HLOV_DWH_DIM_ACCOUNTS_HIST
            set EFFECTIVE_TO = '5999-12-01' 
            where ACCOUNT_NUM in ( 
                        select
                            dwh.ACCOUNT_NUM
                        from HLOV_DWH_DIM_ACCOUNTS_HIST dwh
                        left join HLOV_STG_DELETE_ACCOUNTS stg
                        on dwh.ACCOUNT_NUM = stg.ACCOUNT_NUM
                        where stg.ACCOUNT_NUM is null
                        and dwh.EFFECTIVE_TO = to_date('5999-12-01', 'YYYY-MM-DD')
                        and dwh.DELETED_FLG = '0')""".format(prev_current_date)
curs.execute(ins)
ins = """update HLOV_DWH_DIM_CLIENTS_HIST
            set EFFECTIVE_TO = '5999-12-01' 
            where CLIENT_ID in (               
                        select 
                            dwh.CLIENT_ID
                            from HLOV_DWH_DIM_CLIENTS_HIST dwh
                            left join HLOV_STG_DELETE_CLIENTS stg
                            on dwh.CLIENT_ID = stg.CLIENT_ID
                            where stg.CLIENT_ID is null
                            and dwh.EFFECTIVE_TO = to_date('5999-12-01', 'YYYY-MM-DD')
                            and dwh.DELETED_FLG = '0')""".format(prev_current_date)
curs.execute(ins)
ins = """update HLOV_DWH_DIM_TERMINAL_HIST
            set EFFECTIVE_TO = '5999-12-01'
            where TERMINAL_ID in ( 
                        select dwh.TERMINAL_ID
                            from HLOV_DWH_DIM_TERMINAL_HIST dwh
                            full join HLOV_STG_TERMINAL stg
                            on dwh.terminal_id = stg.terminal_id
                            where stg.terminal_id is null    
                            and dwh.EFFECTIVE_TO = to_date('5999-12-01', 'YYYY-MM-DD')
                            and dwh.DELETED_FLG = '0')""".format(prev_current_date)
curs.execute(ins)
# обновление метадаты
curs.execute("""update
            HLOV_META_PASSPORT_BLACKLIST
            set
            LAST_UPDATE_DT = (select max(ENTRY_DT)
            from HLOV_STG_PASSPORT_BLACKLIST)
            where
            (select max(ENTRY_DT)
            from HLOV_STG_PASSPORT_BLACKLIST) is not NULL""")
curs.execute("""update
            HLOV_META_TRANSACTIONS
            set
            LAST_UPDATE_DT = (select max(TRANS_DATE)
            from HLOV_STG_TRANSACTIONS)
            where
            (select max(TRANS_DATE)
            from HLOV_STG_TRANSACTIONS) is not NULL""")
curs.execute("""update
            HLOV_META_CARDS
            set
            LAST_UPDATE_DT = (select max(coalesce(UPDATE_DT, CREATE_DT)) from HLOV_STG_CARDS)
            where
            (select max(coalesce(UPDATE_DT, CREATE_DT)) from HLOV_STG_CARDS) is not NULL""")
curs.execute("""update
            HLOV_META_ACCOUNTS
            set
            LAST_UPDATE_DT = (select max(coalesce(UPDATE_DT, CREATE_DT)) from HLOV_STG_ACCOUNTS)
            where
            (select max(coalesce(UPDATE_DT, CREATE_DT)) from HLOV_STG_ACCOUNTS) is not NULL""")
curs.execute("""update
            HLOV_META_CLIENTS
            set
            LAST_UPDATE_DT = (select max(coalesce(UPDATE_DT, CREATE_DT)) from HLOV_STG_CLIENTS)
            where
            (select max(coalesce(UPDATE_DT, CREATE_DT)) from HLOV_STG_CLIENTS) is not NULL""")
conn.commit()
# построение итоговой витрины 
curs.execute("""insert into HLOV_REP_FRAUD EVENT_DT
            (EVENT_DT, PASSPORT, FIO, PHONE, EVENT_TYPE, REPORT_DT)
            (select 
            TRANS_DATE, PASSPORT_NUM, 
            LAST_NAME||' '||FIRST_NAME||' '||PATRONYMIC, 
            PHONE, EVENT_TYPE, CURRENT_DATE 
            from
                (select
                CLIENT_ID, LAST_NAME, FIRST_NAME, PATRONYMIC,
                PHONE, TERMINAL_CITY, TRANS_DATE, CARD_NUM, 
                NEXT_CITY, NEXT_DATE, DATE_OF_BIRTH,
                PASSPORT_VALID_TO, VALID_TO, 
                PASSPORT_NUM, BLACK_LIST,
                
                case
                    when TERMINAL_CITY <> NEXT_CITY and (NEXT_DATE - TRANS_DATE) < interval '1' hour
                    then 'different cities'
                    when BLACK_LIST is not null or PASSPORT_VALID_TO < to_date('5999-12-01', 'YYYY-MM-DD HH24-MI-SS')  then 'invalid passport'
                    when VALID_TO < to_date('5999-12-01', 'YYYY-MM-DD HH24-MI-SS') then 'invalid account'
                    when OPER_RESULT = 'SUCCESS' and PREV_RESULT = 'REJECT' and PREVPREV_RESULT = 'REJECT'
                    and AMT < PREV_AMT and PREV_AMT< PREVPREV_AMT
                    and TRANS_DATE - PREVPREV_DATE < interval '20' minute
                    then 'selection amount'
                end EVENT_TYPE
                from
                (select 
                    CLIENT_ID, LAST_NAME, FIRST_NAME, PATRONYMIC,PHONE, 
                    TERMINAL_CITY, TRANS_DATE, CARD_NUM, DATE_OF_BIRTH,
                    PASSPORT_VALID_TO, VALID_TO, PASSPORT_NUM, AMT, 
                    OPER_RESULT, PREV_DATE, PREV_AMT, PREV_RESULT, 
                    NEXT_CITY, NEXT_DATE, BLACK_LIST,
                    lag(PREV_DATE) over (partition by CARD_NUM order by TRANS_DATE) PREVPREV_DATE,
                    lag(PREV_AMT) over (partition by CARD_NUM order by TRANS_DATE) PREVPREV_AMT,
                    lag(PREV_RESULT) over (partition by CARD_NUM order by TRANS_DATE) PREVPREV_RESULT
                    from
                    (select cl.
                        CLIENT_ID,LAST_NAME,FIRST_NAME,PATRONYMIC,PHONE,
                        TERMINAL_CITY, TRANS_DATE, car.CARD_NUM,
                        cl.DATE_OF_BIRTH, cl.PASSPORT_VALID_TO,
                        acc.VALID_TO, pas.PASSPORT_NUM as BLACK_LIST, 
                        cl.PASSPORT_NUM, tra.AMT, OPER_RESULT,
                        lead(TERMINAL_CITY) over (partition by car.CARD_NUM order by TRANS_DATE) NEXT_CITY,
                        lead(TRANS_DATE) over (partition by car.CARD_NUM order by TRANS_DATE) NEXT_DATE,
                        lag(tra.TRANS_DATE) over (partition by tra.CARD_NUM order by tra.TRANS_DATE) PREV_DATE,
                        lag(tra.AMT) over (partition by tra.CARD_NUM order by tra.TRANS_DATE) PREV_AMT,
                        lag(tra.oper_result) over (partition by tra.CARD_NUM order by tra.TRANS_DATE) PREV_RESULT
                            from HLOV_DWH_FACT_TRANSACTIONS tra
                            full join HLOV_DWH_DIM_CARDS_HIST car
                                on tra.CARD_NUM = RTRIM(car.CARD_NUM)
                            full join HLOV_DWH_DIM_ACCOUNTS_HIST acc
                                on acc.ACCOUNT_NUM = car.ACCOUNT_NUM
                            full join HLOV_DWH_DIM_CLIENTS_HIST cl
                                on cl.CLIENT_ID = acc.CLIENT
                            left join HLOV_DWH_FACT_PSSPRT_BLCKLST pas
                                on cl.PASSPORT_NUM = pas.PASSPORT_NUM
                            full join HLOV_DWH_DIM_TERMINAL_HIST tr
                                on tr.TERMINAL_ID = tra.TERMINAL)))
            where EVENT_TYPE is not null)""".format(current_date, current_date))
conn.commit()
curs.close()
conn.close()
# Переименование и перекладка .backup 

os.replace(file_pb, os.path.join('/home/de2tm/HLOV/archive', os.path.basename(file_pb + '.backup')))
os.replace(file_ter, os.path.join('/home/de2tm/HLOV/archive', os.path.basename(file_ter + '.backup')))
os.replace(file_tr, os.path.join('/home/de2tm/HLOV/archive', os.path.basename(file_tr + '.backup')))

