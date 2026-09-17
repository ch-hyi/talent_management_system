import sqlite3
import pandas as pd
from pathlib import Path
import os
import uuid

# 1️⃣ 連線（沒有會自動建立）
conn = None
log = None
user = None
folder_path = Path("C:/Users/rchang4/talent_system/frontend/static/msg_backup")

# 2️⃣ cursor（操作用）
cursor = None
cursor_log = None
cursor_user = None

# 3️⃣ 建表（只要做一次）
def connect():
    global conn
    global log
    global user

    global cursor 
    global cursor_log
    global cursor_user

    conn = sqlite3.connect("C:/Users/rchang4/talent_system/backend/data/104_talent.db")
    log = sqlite3.connect("C:/Users/rchang4/talent_system/backend/data/log.db")
    user = sqlite3.connect("C:/Users/rchang4/talent_system/backend/data/user.db")

    # 2️⃣ cursor（操作用）
    cursor = conn.cursor()
    cursor_log = log.cursor()
    cursor_user = user.cursor()

def create():
    """建立完整的資料庫表格和索引"""
    
    # ==========================================
    # 主表格：talent
    # ==========================================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS talent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,           
        source TEXT,
        source_id TEXT UNIQUE,
        source_link TEXT,
        mail_id TEXT,
        update_time DATETIME,
        recommender TEXT,
        name TEXT,
        score FLOAT,
        score_distance FLOAT,
        score_experience FLOAT,
        score_education FLOAT,
        score_age FLOAT,
        gender TEXT,
        education_department TEXT,
        education_school TEXT,
        education_degree TEXT,
        education_discipline TEXT,
        education_mode TEXT,
        education_status TEXT,
        description TEXT,
        age INTEGER,
        vacancy TEXT,
        city TEXT,
        district TEXT,
        phone TEXT, 
        email TEXT,
        received_time DATETIME,
        current_status TEXT,
        current_company TEXT,
        current_job_title TEXT,
        total_exp_years REAL,
        expected_salary INTEGER,
        note TEXT,
        msg_backup_path TEXT,
        interview_time DATETIME,
        meeting TEXT,
        block INTEGER DEFAULT 0,
        lock_status TEXT,
        block_reason TEXT,
        onboarding_date DATETIME
    )
    """)
    print("✅ talent 表格建立完成")
    
    # ==========================================
    # 第一層：單欄索引
    # ==========================================
    print("🔧 建立單欄索引...")
    
    # 篩選器主要欄位
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_status ON talent (current_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_city ON talent (city);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_source ON talent (source);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_vacancy ON talent (vacancy);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_degree ON talent (education_degree);")
    
    # 搜尋欄位
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_name ON talent (name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_email ON talent (email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_phone ON talent (phone);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_source_id ON talent (source_id);")
    
    # 數值範圍篩選
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_score ON talent (score);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_age ON talent (age);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_exp_years ON talent (total_exp_years);")
    
    # 時間欄位
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_update_time ON talent (update_time);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_received_time ON talent (received_time);")
    
    # 黑名單過濾
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_block ON talent (block);")
    
    # ==========================================
    # 第二層：複合索引（常見組合查詢）
    # ==========================================
    print("🔧 建立複合索引...")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_city_status ON talent (city, current_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_vacancy_status ON talent (vacancy, current_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_score_status ON talent (score, current_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_source_status ON talent (source, current_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_score_time ON talent (score DESC, received_time DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_talent_status_update ON talent (current_status, update_time DESC);")
    
    # ==========================================
    # 第三層：覆蓋索引（極致優化）
    # ==========================================
    print("🔧 建立覆蓋索引...")
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_talent_filter_display 
        ON talent (current_status, city, score DESC, id, name, vacancy, update_time);
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_talent_source_id_detail 
        ON talent (source_id, current_status, score, update_time);
    """)
    
    # ==========================================
    # 第四層：全文搜尋索引（FTS5）✅ 修正版
    # ==========================================
    print("🔧 建立全文搜尋索引...")
    
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS talent_fts 
            USING fts5(
                name, 
                education_school, 
                vacancy, 
                email, 
                description,
                current_company,
                content='talent',
                content_rowid='id'
            );
        """)
        
        # ✅ INSERT 觸發器（不變）
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS talent_fts_insert 
            AFTER INSERT ON talent BEGIN
                INSERT INTO talent_fts(rowid, name, education_school, vacancy, email, description, current_company)
                VALUES (
                    new.id, 
                    COALESCE(new.name, ''), 
                    COALESCE(new.education_school, ''), 
                    COALESCE(new.vacancy, ''),
                    COALESCE(new.email, ''),
                    COALESCE(new.description, ''),
                    COALESCE(new.current_company, '')
                );
            END;
        """)

        # ✅ UPDATE 觸發器（修正版 - 移除 OF 限制）
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS talent_fts_update 
            AFTER UPDATE ON talent
            WHEN (
                old.name IS NOT new.name OR
                old.education_school IS NOT new.education_school OR
                old.vacancy IS NOT new.vacancy OR
                old.email IS NOT new.email OR
                old.description IS NOT new.description OR
                old.current_company IS NOT new.current_company
            )
            BEGIN
                INSERT OR REPLACE INTO talent_fts(rowid, name, education_school, vacancy, email, description, current_company)
                VALUES (
                    new.id, 
                    COALESCE(new.name, ''), 
                    COALESCE(new.education_school, ''), 
                    COALESCE(new.vacancy, ''),
                    COALESCE(new.email, ''),
                    COALESCE(new.description, ''),
                    COALESCE(new.current_company, '')
                );
            END;
        """)
        
        # ✅ DELETE 觸發器（不變）
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS talent_fts_delete 
            AFTER DELETE ON talent BEGIN
                DELETE FROM talent_fts WHERE rowid = old.id;
            END;
        """)
        
        print("✅ FTS5 full-text search enabled!")
    except Exception as e:
        print(f"⚠️ FTS5 setup failed: {e}")
    
    # ==========================================
    # Log 表格
    # ==========================================
    cursor_log.execute("""
        CREATE TABLE IF NOT EXISTS log (
            log_id TEXT PRIMARY KEY,             
            source TEXT,
            source_id TEXT NOT NULL,           
            name TEXT,
            version INTEGER NOT NULL,         
            operator TEXT,                       
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            snapshot_json TEXT,        
            status TEXT,                      
            action TEXT, 
            previous_version INTEGER,                  
            vacancy TEXT,                         
            note TEXT,                      
            meeting TEXT,                  
            operate_status TEXT, 
            changed_info TEXT,
            raw_text TEXT,      
            error_message TEXT 
        );
    """)
    print("✅ log 表格建立完成")
    
    # Log 表格索引
    cursor_log.execute("CREATE INDEX IF NOT EXISTS idx_log_source_id ON log (source_id);")
    cursor_log.execute("CREATE INDEX IF NOT EXISTS idx_log_timestamp ON log (timestamp DESC);")
    cursor_log.execute("CREATE INDEX IF NOT EXISTS idx_log_version ON log (source_id, version);")
    
    print("✅ 所有表格和索引建立完成！")

def create_new_table():
    connect()
    cursor_user.execute("""
    CREATE TABLE IF NOT EXISTS user (
        user_id TEXT PRIMARY KEY,

        user_account TEXT NOT NULL UNIQUE,
        user_name TEXT NOT NULL,
        user_email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,

        user_role TEXT,

        status TEXT NOT NULL DEFAULT 'ACTIVE',

        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT,

        update_time DATETIME,
        updated_by TEXT,

        deleted_time DATETIME,
        deleted_by TEXT,

        last_login DATETIME,

    )
    """)

    indexes = [
        """
        CREATE INDEX IF NOT EXISTS idx_user_account
        ON user(user_account)
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_user_name
        ON user(user_name)
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_user_role
        ON user(user_role)
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_user_last_login
        ON user(last_login)
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_user_create_time
        ON user(create_time)
        """,

        """
        CREATE INDEX IF NOT EXISTS idx_user_status_create_time
        ON user(status, create_time)
        """
    ]

    for sql in indexes:
        cursor_user.execute(sql)
    user.commit()


def create_vacancy_tables():
    connect()

    try:
        # SQLite 每次建立連線後都要開啟外鍵約束
        cursor_user.execute("PRAGMA foreign_keys = ON")

        # =====================================================
        # 1. 職缺表
        # =====================================================
        cursor_user.execute("""
            CREATE TABLE IF NOT EXISTS vacancy (
                vacancy_id TEXT PRIMARY KEY,

                position_title TEXT NOT NULL,
                introduction TEXT,
                compensation TEXT,
                requirements TEXT,
                work_location TEXT,
                manager TEXT,
                senior TEXT,
                lab TEXT,
                weight TEXT,

                education_score_error TEXT,
                education_score_5 TEXT,
                education_score_4 TEXT,
                education_score_3 TEXT,
                education_score_2 TEXT,
                education_score_1 TEXT,
                education_score_0 TEXT,

                status TEXT NOT NULL DEFAULT 'ACTIVE',

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # =====================================================
        # 2. 職缺與使用者關聯表
        # =====================================================
        cursor_user.execute("""
            CREATE TABLE IF NOT EXISTS vacancy_incharge (
                relation_id TEXT PRIMARY KEY,

                vacancy_id TEXT NOT NULL,
                user_id TEXT NOT NULL,

                role TEXT NOT NULL DEFAULT 'guest',

                is_primary INTEGER NOT NULL DEFAULT 0
                    CHECK (is_primary IN (0, 1)),

                assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                unassigned_at TEXT,
                note TEXT,

                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (vacancy_id)
                    REFERENCES vacancy(vacancy_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT,

                FOREIGN KEY (user_id)
                    REFERENCES user(user_id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT,

                FOREIGN KEY (created_by)
                    REFERENCES user(user_id)
                    ON UPDATE CASCADE
                    ON DELETE SET NULL,

                CHECK (
                    unassigned_at IS NULL
                    OR unassigned_at >= assigned_at
                )
            )
        """)

        # =====================================================
        # 3. Vacancy 索引
        # =====================================================

        # 依職位搜尋
        cursor_user.execute("""
            CREATE INDEX IF NOT EXISTS idx_vacancy_position_title
            ON vacancy(position_title)
        """)

        # 依狀態篩選
        cursor_user.execute("""
            CREATE INDEX IF NOT EXISTS idx_vacancy_status
            ON vacancy(status)
        """)

        # 依 Lab 篩選
        cursor_user.execute("""
            CREATE INDEX IF NOT EXISTS idx_vacancy_lab
            ON vacancy(lab)
        """)

        # 依 Senior 篩選
        cursor_user.execute("""
            CREATE INDEX IF NOT EXISTS idx_vacancy_senior
            ON vacancy(senior)
        """)

        # 依上班地點篩選
        cursor_user.execute("""
            CREATE INDEX IF NOT EXISTS idx_vacancy_work_location
            ON vacancy(work_location)
        """)

        # 職缺列表：狀態＋最後修改時間
        cursor_user.execute("""
            CREATE INDEX IF NOT EXISTS idx_vacancy_status_updated
            ON vacancy(status, updated_at DESC)
        """)

        # =====================================================
        # 4. In-charge 關聯表索引
        # =====================================================

        # 透過 user_id 查其負責過的職缺
        cursor_user.execute("""
            CREATE INDEX IF NOT EXISTS idx_incharge_user
            ON vacancy_incharge(user_id)
        """)

        # 透過 vacancy_id 查歷史負責人
        cursor_user.execute("""
            CREATE INDEX IF NOT EXISTS idx_incharge_vacancy
            ON vacancy_incharge(vacancy_id)
        """)

        # 查某人目前負責的職缺
        cursor_user.execute("""
            CREATE INDEX IF NOT EXISTS idx_incharge_user_current
            ON vacancy_incharge(user_id, vacancy_id)
            WHERE unassigned_at IS NULL
        """)

        # 查某職缺目前的負責人
        cursor_user.execute("""
            CREATE INDEX IF NOT EXISTS idx_incharge_vacancy_current
            ON vacancy_incharge(vacancy_id, user_id)
            WHERE unassigned_at IS NULL
        """)

        # 防止同一個人在同一職缺中重複擁有相同有效角色
        cursor_user.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_incharge_current_role
            ON vacancy_incharge(
                vacancy_id,
                user_id,
                role_type
            )
            WHERE unassigned_at IS NULL
        """)

        user.commit()
        print("vacancy、vacancy_incharge 與索引建立完成")

    except Exception:
        user.rollback()
        raise

    finally:
        cursor.close()

def create_share_table():
    connect()
    cursor.execute("""
            CREATE TABLE share (
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                share_id TEXT NOT NULL,
                created_time TEXT NOT NULL,
                expired_time TEXT,
                PRIMARY KEY (source, source_id)
            )
        """)


def import_vacancy_excel():
    connect()
    column_mapping = {
        "職位": "position_title",
        "介紹": "introduction",
        "待遇": "compensation",
        "條件": "requirements",
        "上班地點": "work_location",
        "Senior": "senior",
        "Lab": "lab",
        "Weight": "weight",
        "學歷要求-錯誤": "education_score_error",
        "學歷要求-5": "education_score_5",
        "學歷要求-4": "education_score_4",
        "學歷要求-3": "education_score_3",
        "學歷要求-2": "education_score_2",
        "學歷要求-1": "education_score_1",
        "學歷要求-0": "education_score_0",
        "狀態": "status",
    }
    df  = pd.read_excel("c:/Users/rchang4/talent_system/backend/data/jd_fake.xlsx")
    # Excel 中文欄位改成資料庫欄位
    df = df.rename(columns=column_mapping)

    # 只取需要的欄位
    database_columns = list(column_mapping.values())
    df = df[database_columns]

    # 每筆職缺產生 UUID
    df.insert(
        0,
        "vacancy_id",
        [str(uuid.uuid4()) for _ in range(len(df))]
    )

    # NaN 轉成 None
    df = df.astype(object).where(pd.notna(df), None)

    sql = """
        INSERT INTO vacancy (
            vacancy_id,
            position_title,
            introduction,
            compensation,
            requirements,
            work_location,
            senior,
            lab,
            weight,
            education_score_error,
            education_score_5,
            education_score_4,
            education_score_3,
            education_score_2,
            education_score_1,
            education_score_0,
            status
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?
        )
    """

    user.executemany(
        sql,
        df[
            [
                "vacancy_id",
                "position_title",
                "introduction",
                "compensation",
                "requirements",
                "work_location",
                "senior",
                "lab",
                "weight",
                "education_score_error",
                "education_score_5",
                "education_score_4",
                "education_score_3",
                "education_score_2",
                "education_score_1",
                "education_score_0",
                "status",
            ]
        ].itertuples(index=False, name=None)
    )

    user.commit()

    print(f"成功寫入 {len(df)} 筆職缺資料")

def search_db(query):
    """查詢 talent 資料庫"""

    connect()
    cursor.execute(query)
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    return rows

def search_vacancy(query):
    """查詢 vacancy 資料庫"""

    connect()
    cursor_user.execute(query)
    rows = cursor_user.fetchall()
    for row in rows:
        print(row)
    return rows

def search_log(query):
    """查詢 log 資料庫"""
    cursor_log.execute(query)
    rows = cursor_log.fetchall()
    for row in rows:
        print(row)
    return rows

def export():
    """匯出資料庫為 Excel"""
    df_talent = pd.read_sql("SELECT * FROM talent", conn)
    df_talent.to_excel("C:/Users/rchang4/auto_resume/talent.xlsx", index=False)
    
    df_log = pd.read_sql("SELECT * FROM log", log)
    df_log.to_excel("C:/Users/rchang4/auto_resume/log.xlsx", index=False)
    
    print("✅ 資料已匯出至 Excel")

def delete_vacancy_table():
    connect()
    cursor_user.execute("DROP TABLE IF EXISTS vacancy;")
    cursor_user.execute("DROP TABLE IF EXISTS vacancy_incharge;")
    user.commit()


def delete_table():
    """完全刪除所有表格和觸發器"""
    try:
        # 刪除 FTS5 相關物件
        cursor.execute("DROP TRIGGER IF EXISTS talent_fts_insert;")
        cursor.execute("DROP TRIGGER IF EXISTS talent_fts_update;")
        cursor.execute("DROP TRIGGER IF EXISTS talent_fts_delete;")
        cursor.execute("DROP TABLE IF EXISTS talent_fts;")
        
        # 刪除主表格
        cursor.execute("DROP TABLE IF EXISTS talent;")
        cursor_log.execute("DROP TABLE IF EXISTS log;")
        
        conn.commit()
        log.commit()
        
        print("✅ 資料庫表格已刪除")
    except Exception as e:
        print(f"⚠️ 刪除表格時發生錯誤: {e}")
    
    # 清空備份資料夾
    if not folder_path.exists():
        print(f"資料夾不存在: {folder_path}")
        return

    for item in folder_path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                import shutil
                shutil.rmtree(item)
        except Exception as e:
            print(f"刪除 {item.name} 時發生錯誤: {e}")
    conn.close()
    log.close()
    print("✅ 備份資料夾已清空")

def delete_file ():
    for db_file in ['104_talent.db', 'log.db']:
        db_path = f"C:/Users/rchang4/talent_system/backend/data/{db_file}"
        for ext in ['', '-wal', '-shm', '-journal']:
            try:
                os.remove(db_path + ext)
                print(f"✅ 已刪除 {db_file}{ext}")
            except FileNotFoundError:
                pass

def modify(idx, target, source_id, value):
    """更新資料庫欄位"""
    db = ["log", "talent"]
    connect()
    sql_query = f"""
        UPDATE {db[idx]} 
        SET {target} = ? 
        WHERE source_id = ?
    """
    try:
        if idx == 0:
            cursor_log.execute(sql_query, (value, source_id))
            log.commit()
        else:
            cursor.execute(sql_query, (value, source_id))
            conn.commit()
        print(f"✅ 已更新 {db[idx]}.{target} = {value} (source_id: {source_id})")
    except Exception as e:
        print(f"❌ 更新失敗: {e}")

def test_update():
    """測試更新功能（驗證 FTS5 修復）"""
    print("\n🧪 測試更新功能...")
    
    try:
        # 插入測試資料
        cursor.execute("""
            INSERT OR REPLACE INTO talent (source, source_id, name, email, vacancy) 
            VALUES ('test', 'test001', 'Test User', 'old@example.com', 'Engineer')
        """)
        conn.commit()
        print("✅ 測試資料插入成功")
        
        # 更新 email（之前會導致資料庫損壞的操作）
        cursor.execute("""
            UPDATE talent 
            SET email = 'new@example.com' 
            WHERE source_id = 'test001'
        """)
        conn.commit()
        print("✅ Email 更新成功（FTS5 觸發器正常運作）")
        
        # 驗證更新
        cursor.execute("SELECT name, email FROM talent WHERE source_id = 'test001'")
        result = cursor.fetchone()
        print(f"✅ 驗證結果: {result}")
        
        # 清理測試資料
        cursor.execute("DELETE FROM talent WHERE source_id = 'test001'")
        conn.commit()
        print("✅ 測試資料已清理\n")
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}\n")

def unlock(source,id):
    connect()
    query = """UPDATE talent SET lock_status = 'unlocked' WHERE source = ? AND source_id = ?"""
    cursor.execute(query,(source,id))
    conn.commit()
    print("解鎖成功")

def reconstruct():
    print("=" * 50)
    print("🚀 開始重建資料庫...")
    print("=" * 50)
    # 刪除舊表格
    connect()
    delete_table()
    delete_file()
    # 建立新表格
    connect()
    create()
    # 提交變更
    conn.commit()
    log.commit()
    # 測試更新功能
    test_update()
    print("=" * 50)
    print("✅ 資料庫重建完成！")
    print("=" * 50)

def alter_table():
    """安全地新增審核欄位到 talent 表"""
    
    connect()
    
    try:
        # 開始交易
        conn.execute("BEGIN TRANSACTION")
        
        # 檢查欄位是否已存在 (避免重複執行報錯)
        cursor.execute("PRAGMA table_info(talent)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        # 新增 review_status 欄位
        if 'review_status' not in existing_columns:
            cursor.execute("""
                ALTER TABLE talent 
                ADD COLUMN review_status TEXT DEFAULT NULL
            """)
            print("已新增 review_status 欄位")
        else:
            print("ℹreview_status 欄位已存在，跳過")
        
        # 新增 review_reason 欄位
        if 'review_reason' not in existing_columns:
            cursor.execute("""
                ALTER TABLE talent 
                ADD COLUMN review_reason TEXT DEFAULT NULL
            """)
            print("已新增 review_reason 欄位")
        else:
            print("ℹreview_reason 欄位已存在，跳過")

        # 新增 reviewer 欄位
        if 'reviewer' not in existing_columns:
            cursor.execute("""
                ALTER TABLE talent 
                ADD COLUMN reviewer TEXT DEFAULT NULL
            """)
            print("已新增 reviewer 欄位")
        else:
            print("ℹreviewer 欄位已存在，跳過")
        
        
        # 提交交易
        conn.commit()
        print("\n資料庫欄位已更新")
        
        # 驗證結果
        cursor.execute("PRAGMA table_info(talent)")
        columns = cursor.fetchall()
        print(f"\n talent 表目前有 {len(columns)} 欄")
        
    except Exception as e:
        # 發生錯誤時回滾
        conn.rollback()
        print(f"❌ 錯誤: {e}")
        raise
    
    finally:
        conn.close()

def create_user():
    connect()
    cursor_user.execute("""
    INSERT INTO user (
        user_id,
        user_account,
        user_name,
        user_email,
        password_hash,
        user_role,
        created_by,
        vacancies_in_charge
    )
    VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?
    )
    """, (
        str(uuid.uuid4()),
        "rchang4",
        "Richard Chang",
        "richard.chang@bureauveritas.com",
        "$2b$12$iOprlR/.rvr.nPxHq17QBec/QRpEoC20CyTba7PKgK0AuzwSoFvzW",
        "admin",
        "self",
        "vacancies_in_charge"))
    user.commit()

def all():
    connect()
    cursor_user.execute("""
    SELECT * FROM vacancy_incharge
""",)
    result = cursor_user.fetchall()
    print(result)

def search_user():
    connect()
    cursor_user.execute("""
    SELECT * FROM user 
""",())
    result = cursor_user.fetchall()
    print(result)

def search_lab():
    connect()
    cursor_user.execute("""
    SELECT * FROM lab 
""",())
    result = cursor_user.fetchall()
    print(result)

def status_change():
    connect()
    cursor.execute("""
UPDATE talent
SET current_status = 'AI REVIEW-NOT PASS'
WHERE score < 60;
""")
    conn.commit()


def create_ocr_draft():
    connect()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ocr_draft (
        draft_id TEXT PRIMARY KEY,

        creator TEXT NOT NULL,

        file_path TEXT NOT NULL,

        status TEXT NOT NULL,

        result_json TEXT,

        error_msg TEXT,

        created_time TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()

def search_ocr():
    connect()
    cursor.execute("""SELECT * FROM ocr_draft""")
    result = cursor.fetchall()
    print(result)

def delete_ocr_data():
    connect()

    cursor.execute("DELETE FROM ocr_draft")

    conn.commit()

def create_lab_table():
    connect()
    cursor_user.execute("""
    CREATE TABLE IF NOT EXISTS lab (
        lab_id TEXT PRIMARY KEY,

        name TEXT NOT NULL,

        address TEXT NOT NULL,

        latitude REAL,
        longitude REAL,
        template TEXT ,
        contact TEXT,

        created_time TEXT DEFAULT CURRENT_TIMESTAMP
    )

""")
    user.commit()

def upload_lab():
    connect()
    labs = [
    (str(uuid.uuid4()), "華亞", "桃園市龜山區華亞二路19號", 25.05051, 121.3785),
    (str(uuid.uuid4()), "文明", "桃園市龜山區文明路70號", 25.05429, 121.3797),
    (str(uuid.uuid4()), "林口", "新北市林口區嘉寶里14鄰寶斗厝坑47-2號", 25.11145, 121.3449),
    (str(uuid.uuid4()), "竹南", "苗栗縣竹南鎮延平路182號", 24.6915, 120.8737),
    (str(uuid.uuid4()), "芎林", "新竹縣芎林鄉文德路206巷49號", 24.78154, 121.0804),
    (str(uuid.uuid4()), "竹科", "新竹市力行一路1號E2棟", 24.77392, 121.0161),
    ]

    cursor_user.executemany(
        """
        INSERT INTO lab (
            lab_id,
            name,
            address,
            latitude,
            longitude
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        labs
    )

    user.commit()

def search_share():
    connect()
    cursor.execute("""SELECT * FROM share""")
    result = cursor.fetchall()
    print(result)

# ==========================================
# 主程式執行區
# ==========================================
if __name__ == "__main__":
    # create_new_table()
    # delete_vacancy_table()
    # create_user()
    # alter_table()
    # 其他功能（需要時取消註解）
    # search_db("""SELECT * FROM talent WHERE source_id = 20000002563379""")
    # upload_lab()
    # search_lab()
    # delete_ocr_data()
    # search_ocr()
    search_share()
    # search_log("SELECT * FROM log LIMIT 5;")
    # create_ocr_draft()
    # search_vacancy("SELECT * FROM vacancy LIMIT 1000;")
    # modify(1, "review_status", "1829975760042", "")
    # export()
    # create_vacancy_tables()
    # import_vacancy_excel()
    # unlock("104","30000003291720")
    # status_change()