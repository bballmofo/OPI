# pip install python-dotenv
# pip install psycopg2-binary

import os, sys, requests
from dotenv import load_dotenv
import traceback, time, codecs, json
import psycopg2
import hashlib

if not os.path.isfile('.env'):
  print(".env file not found, please run \"python3 reset_init.py\" first")
  sys.exit(1)

## global variables
ticks = {}
in_commit = False
block_events_str = ""
EVENT_SEPARATOR = "|"
INDEXER_VERSION = "opi-grc20-full-node v0.4.0"
RECOVERABLE_DB_VERSIONS = [  ]
DB_VERSION = 4
EVENT_HASH_VERSION = 2

SELF_MINT_ENABLE_HEIGHT = 837090

## psycopg2 doesn't get decimal size from postgres and defaults to 28 which is not enough for grc-20 so we use long which is infinite for integers
DEC2LONG = psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values,
    'DEC2LONG',
    lambda value, curs: int(value) if value is not None else None)
psycopg2.extensions.register_type(DEC2LONG)

## load env variables
load_dotenv()
db_user = os.getenv("DB_USER") or "postgres"
db_host = os.getenv("DB_HOST") or "localhost"
db_port = int(os.getenv("DB_PORT") or "5432")
db_database = os.getenv("DB_DATABASE") or "postgres"
db_password = os.getenv("DB_PASSWD")
db_metaprotocol_user = os.getenv("DB_METAPROTOCOL_USER") or "postgres"
db_metaprotocol_host = os.getenv("DB_METAPROTOCOL_HOST") or "localhost"
db_metaprotocol_port = int(os.getenv("DB_METAPROTOCOL_PORT") or "5432")
db_metaprotocol_database = os.getenv("DB_METAPROTOCOL_DATABASE") or "postgres"
db_metaprotocol_password = os.getenv("DB_METAPROTOCOL_PASSWD")
report_to_indexer = (os.getenv("REPORT_TO_INDEXER") or "true") == "true"
report_url = os.getenv("REPORT_URL") or "https://api.opi.network/report_block"
report_retries = int(os.getenv("REPORT_RETRIES") or "10")
report_name = os.getenv("REPORT_NAME") or "opi_grc20_indexer"
create_extra_tables = (os.getenv("CREATE_EXTRA_TABLES") or "false") == "true"
network_type = os.getenv("NETWORK_TYPE") or "mainnet"

first_inscription_heights = {
  'mainnet': 767430,
  'testnet': 2581400,
  'signet': 188171,
  'regtest': 0,
}
first_inscription_height = first_inscription_heights[network_type]

first_grc20_heights = {
  'mainnet': 836510,
  'testnet': 2581400,
  'signet': 188171,
  'regtest': 0,
}
first_grc20_height = first_grc20_heights[network_type]

if network_type == 'regtest':
  report_to_indexer = False
  print("Network type is regtest, reporting to indexer is disabled.")

## connect to db
conn = psycopg2.connect(
  host=db_host,
  port=db_port,
  database=db_database,
  user=db_user,
  password=db_password)
conn.autocommit = True
cur = conn.cursor()

conn_metaprotocol = psycopg2.connect(
  host=db_metaprotocol_host,
  port=db_metaprotocol_port,
  database=db_metaprotocol_database,
  user=db_metaprotocol_user,
  password=db_metaprotocol_password)
conn_metaprotocol.autocommit = True
cur_metaprotocol = conn_metaprotocol.cursor()

## create tables if not exists
## does grc20_block_hashes table exist?
cur.execute('''SELECT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'grc20_block_hashes') AS table_existence;''')
if cur.fetchone()[0] == False:
  print("Initialising database...")
  with open('db_init.sql', 'r') as f:
    sql = f.read()
    cur.execute(sql)
  conn.commit()

if create_extra_tables:
  pass


cur_metaprotocol.execute('SELECT network_type from ord_network_type LIMIT 1;')
if cur_metaprotocol.rowcount == 0:
  print("ord_network_type not found, main db needs to be recreated from scratch or fixed with index.js, please run index.js in main_index")
  sys.exit(1)

network_type_db = cur_metaprotocol.fetchone()[0]
if network_type_db != network_type:
  print("network_type mismatch between main index and grc20 index", network_type_db, network_type)
  sys.exit(1)

cur_metaprotocol.execute('SELECT event_type, max_transfer_cnt from ord_transfer_counts;')
if cur_metaprotocol.rowcount == 0:
  print("ord_transfer_counts not found, please run index.js in main_index to fix db")
  sys.exit(1)

default_max_transfer_cnt = 0
tx_limits = cur_metaprotocol.fetchall()
for tx_limit in tx_limits:
  if tx_limit[0] == 'default':
    default_max_transfer_cnt = tx_limit[1]
    break

if default_max_transfer_cnt < 2:
  print("default max_transfer_cnt is less than 2, grc20_indexer requires at least 2, please recreate db from scratch and rerun ord with default tx limit set to 2 or more")
  sys.exit(1)

## helper functions

def utf8len(s):
  return len(s.encode('utf-8'))

def is_positive_number(s, do_strip=False):
  try:
    if do_strip:
      s = s.strip()
    try:
      if len(s) == 0: return False
      for ch in s:
        if ord(ch) > ord('9') or ord(ch) < ord('0'):
          return False
      return True
    except KeyboardInterrupt:
      raise KeyboardInterrupt
    except: return False
  except KeyboardInterrupt:
    raise KeyboardInterrupt
  except: return False ## has to be a string

def is_positive_number_with_dot(s, do_strip=False):
  try:
    if do_strip:
      s = s.strip()
    try:
      dotFound = False
      if len(s) == 0: return False
      if s[0] == '.': return False
      if s[-1] == '.': return False
      for ch in s:
        if ord(ch) > ord('9') or ord(ch) < ord('0'):
          if ch != '.': return False
          if dotFound: return False
          dotFound = True
      return True
    except KeyboardInterrupt:
      raise KeyboardInterrupt
    except: return False
  except KeyboardInterrupt:
    raise KeyboardInterrupt
  except: return False ## has to be a string

def get_number_extended_to_18_decimals(s, decimals, do_strip=False):
  if do_strip:
    s = s.strip()
  
  if '.' in s:
    normal_part = s.split('.')[0]
    if len(s.split('.')[1]) > decimals or len(s.split('.')[1]) == 0: ## more decimal digit than allowed or no decimal digit after dot
      return None
    decimals_part = s.split('.')[1][:decimals]
    decimals_part += '0' * (18 - len(decimals_part))
    return int(normal_part + decimals_part)
  else:
    return int(s) * 10 ** 18

def fix_numstr_decimals(num_str, decimals):
  if len(num_str) <= 18:
    num_str = '0' * (18 - len(num_str)) + num_str
    num_str = '0.' + num_str
    if decimals < 18:
      num_str = num_str[:-18+decimals]
  else:
    num_str = num_str[:-18] + '.' + num_str[-18:]
    if decimals < 18:
      num_str = num_str[:-18+decimals]
  if num_str[-1] == '.': num_str = num_str[:-1] ## remove trailing dot
  return num_str

def get_event_str(event, event_type, inscription_id):
  global ticks
  if event_type == "mint-inscribe":
    decimals_int = ticks[event["tick"]][event["code"]][4]
    res = "mint-inscribe;"
    res += inscription_id + ";"
    res += event["minted_pkScript"] + ";"
    res += event["tick"] + ";"
    res += event["code"] + ";"
    res += fix_numstr_decimals(event["amount"], decimals_int) + ";"
    res += event["parent_id"]
    return res
  else:
    print("EVENT TYPE ERROR!!")
    exit(1)

def get_sha256_hash(s):
  return hashlib.sha256(s.encode('utf-8')).hexdigest()


def reset_caches():
  global  ticks
  sttm = time.time()
  cur.execute('''select tick, code, max_tick_supply, max_code_supply,  tick_remaining_supply, code_remaining_supply, decimals from grc20_tickers;''')
  ticks_ = cur.fetchall()
  ticks = {}
  for t in ticks_:
    if t[0] not in ticks:
      ticks[t[0]] = {}
    ticks[t[0]][t[1]] = [t[2], t[3], t[4], t[5], t[6]]
  print("Ticks refreshed in " + str(time.time() - sttm) + " seconds")

block_start_max_event_id = None
grc20_events_insert_sql = '''insert into grc20_events (id, tick, event_type, block_height, inscription_id, event) values '''
grc20_events_insert_cache = []
grc20_tickers_insert_sql = '''insert into grc20_tickers (tick, original_tick, max_supply, decimals, limit_per_mint, remaining_supply, block_height, is_self_mint, deploy_inscription_id) values '''
grc20_tickers_remaining_supply_update_sql = '''update grc20_tickers set tick_remaining_supply = tick_remaining_supply - %s  where tick = %s;'''
grc20_tickers_remaining_supply_update_cache = {}
grc20_tickers_code_remaining_supply_update_sql = '''update grc20_tickers set code_remaining_supply = code_remaining_supply - %s where tick = %s and code = %s;'''
grc20_tickers_code_remaining_supply_update_cache = {}
grc20_code_remaining_supply_update_cache = {}
grc20_collection_insert_sql = '''insert into grc20_collections (tick, code, inscription_id, block_height) values '''
grc20_collection_insert_cache = []

def mint_inscribe(block_height, inscription_id, minted_pkScript, minted_wallet, tick, code, amount, parent_id):
  global ticks, in_commit, block_events_str, event_types

  event = {
    "minted_pkScript": minted_pkScript,
    "minted_wallet": minted_wallet,
    "tick": tick,
    "code": code,
    "amount": str(amount),
    "parent_id": parent_id
  }
  block_events_str += get_event_str(event, "mint-inscribe", inscription_id) + EVENT_SEPARATOR
  event_id = block_start_max_event_id + len(grc20_events_insert_cache) + 1
  grc20_events_insert_cache.append((event_id, tick, event_types["mint-inscribe"], block_height, inscription_id, json.dumps(event)))
  grc20_tickers_remaining_supply_update_cache[tick] = grc20_tickers_remaining_supply_update_cache.get(tick,0) + amount
  if tick not in grc20_code_remaining_supply_update_cache:
    grc20_code_remaining_supply_update_cache[tick] = {}
  if code not in grc20_code_remaining_supply_update_cache[tick]:
    grc20_code_remaining_supply_update_cache[tick][code] = 0
  grc20_code_remaining_supply_update_cache[tick][code] = grc20_code_remaining_supply_update_cache.get(tick, {}).get(code,0) + amount

  grc20_collection_insert_cache.append((tick, code, inscription_id, block_height))
  ticks[tick][code][2] -= amount
  ticks[tick][code][3] -= amount

def update_event_hashes(block_height):
  global block_events_str
  if len(block_events_str) > 0 and block_events_str[-1] == EVENT_SEPARATOR: block_events_str = block_events_str[:-1] ## remove last separator
  block_event_hash = get_sha256_hash(block_events_str)
  cumulative_event_hash = None
  cur.execute('''select cumulative_event_hash from grc20_cumulative_event_hashes where block_height = %s;''', (block_height - 1,))
  if cur.rowcount == 0:
    cumulative_event_hash = block_event_hash
  else:
    cumulative_event_hash = get_sha256_hash(cur.fetchone()[0] + block_event_hash)
  cur.execute('''INSERT INTO grc20_cumulative_event_hashes (block_height, block_event_hash, cumulative_event_hash) VALUES (%s, %s, %s);''', (block_height, block_event_hash, cumulative_event_hash))

def index_block(block_height, current_block_hash):
  global ticks, block_events_str, block_start_max_event_id, grc20_events_insert_cache, grc20_collection_insert_cache, grc20_tickers_remaining_supply_update_cache, grc20_code_remaining_supply_update_cache, in_commit
  print("Indexing block " + str(block_height))
  block_events_str = ""

  if block_height < first_grc20_height:
    print("Block height is before first grc20 height, skipping")
    update_event_hashes(block_height)
    cur.execute('''INSERT INTO grc20_block_hashes (block_height, block_hash) VALUES (%s, %s);''', (block_height, current_block_hash))
    return
  
  cur_metaprotocol.execute('''SELECT ot.inscription_id, ot.old_satpoint, ot.new_pkscript, ot.new_wallet, ot.sent_as_fee, oc."content", oc.content_type, onti.parent_id
                              FROM ord_transfers ot
                              LEFT JOIN ord_content oc ON ot.inscription_id = oc.inscription_id
                              LEFT JOIN ord_number_to_id onti ON ot.inscription_id = onti.inscription_id
                              WHERE ot.block_height = %s AND COALESCE(ot.old_satpoint, '') = ''
                                 AND oc."content" is not null AND oc."content"->>'p'='grc-20'
                              ORDER BY ot.id asc;''', (block_height,))
  transfers = cur_metaprotocol.fetchall()
  if len(transfers) == 0:
    print("No transfers found for block " + str(block_height))
    update_event_hashes(block_height)
    cur.execute('''INSERT INTO grc20_block_hashes (block_height, block_hash) VALUES (%s, %s);''', (block_height, current_block_hash))
    return
  print("Transfer count: ", len(transfers))


  cur.execute('''select COALESCE(max(id), -1) from grc20_events;''')
  block_start_max_event_id = cur.fetchone()[0]
  grc20_events_insert_cache = []
  grc20_collection_insert_cache = []
  grc20_tickers_remaining_supply_update_cache = {}
  grc20_code_remaining_supply_update_cache = {}
  
  idx = 0
  for transfer in transfers:
    idx += 1
    if idx % 100 == 0:
      print(idx, '/', len(transfers))
    

    inscr_id, old_satpoint, new_pkScript, new_addr, sent_as_fee, js, content_type, parent_id = transfer
    if parent_id is None: parent_id = ""
    
    if sent_as_fee and old_satpoint == '': continue ## inscribed as fee

    if content_type is None: continue ## invalid inscription
    try: content_type = codecs.decode(content_type, "hex").decode('utf-8')
    except KeyboardInterrupt:
      raise KeyboardInterrupt
    except: pass
    content_type = content_type.split(';')[0]
    if content_type != 'application/json' and content_type != 'text/plain': continue ## invalid inscription
    # {
    #     "p": "grc-20",
    #     "game": "battle",
    #     "class": "war_machine",
    #     "code": "08AUD00sQ",
    #     "op": "loot"
    # }

    if "game" not in js: continue ## invalid inscription
    if "code" not in js: continue ## invalid inscription
    tick = js["game"]
    code = js["code"]
    try: tick = tick.lower()
    except KeyboardInterrupt:
      raise KeyboardInterrupt
    except: continue ## invalid tick
    try: code = code.lower()
    except KeyboardInterrupt:
      raise KeyboardInterrupt
    except: continue ## invalid code

    # handle mint
    if tick not in ticks.keys(): continue ## not deployed
    if code not in ticks[tick].keys(): continue ## not deployed

    amount = 1
    if ticks[tick][code][2] <= 0: continue ## tick ended
    if ticks[tick][code][3] <= 0: continue ## code ended
    mint_inscribe(block_height, inscr_id, new_pkScript, new_addr, tick, code, amount, parent_id)
    
  
  cur.execute("BEGIN;")
  in_commit = True
  execute_batch_insert(grc20_events_insert_sql, grc20_events_insert_cache, 1000)
  for tick in grc20_tickers_remaining_supply_update_cache:
    cur.execute(grc20_tickers_remaining_supply_update_sql, (grc20_tickers_remaining_supply_update_cache[tick], tick))

  for tick in grc20_code_remaining_supply_update_cache:
    for code in grc20_code_remaining_supply_update_cache[tick]:
      cur.execute(grc20_tickers_code_remaining_supply_update_sql, (grc20_code_remaining_supply_update_cache[tick][code], tick, code))

  execute_batch_insert(grc20_collection_insert_sql, grc20_collection_insert_cache, 1000)
  update_event_hashes(block_height)
  # end of block
  cur.execute('''INSERT INTO grc20_block_hashes (block_height, block_hash) VALUES (%s, %s);''', (block_height, current_block_hash))
  print("committing...")
  cur.execute("COMMIT;")
  in_commit = False
  conn.commit()
  print("ALL DONE")

def execute_batch_insert(sql_start, cache, batch_size):
  if len(cache) > 0:
    single_elem_cnt = len(cache[0])
    single_insert_sql_part = '(' + ','.join(['%s' for _ in range(single_elem_cnt)]) + ')'
    for i in range(0, len(cache), batch_size):
      elem_cnt = min(batch_size, len(cache) - i)
      sql = sql_start + ','.join([single_insert_sql_part for _ in range(elem_cnt)]) + ';'
      cur.execute(sql, [elem for sublist in cache[i:i+batch_size] for elem in sublist])


def check_for_reorg():
  cur.execute('select block_height, block_hash from grc20_block_hashes order by block_height desc limit 1;')
  if cur.rowcount == 0: return None ## nothing indexed yet
  last_block = cur.fetchone()

  cur_metaprotocol.execute('select block_height, block_hash from block_hashes where block_height = %s;', (last_block[0],))
  last_block_ord = cur_metaprotocol.fetchone()
  if last_block_ord[1] == last_block[1]: return None ## last block hashes are the same, no reorg

  print("REORG DETECTED!!")
  cur.execute('select block_height, block_hash from grc20_block_hashes order by block_height desc limit 10;')
  hashes = cur.fetchall() ## get last 10 hashes
  for h in hashes:
    cur_metaprotocol.execute('select block_height, block_hash from block_hashes where block_height = %s;', (h[0],))
    block = cur_metaprotocol.fetchone()
    if block[1] == h[1]: ## found reorg height by a matching hash
      print("REORG HEIGHT FOUND: " + str(h[0]))
      return h[0]
  
  ## bigger than 10 block reorg is not supported by ord
  print("CRITICAL ERROR!!")
  sys.exit(1)

def reorg_fix(reorg_height):
  global event_types
  cur.execute('begin;')
  # cur.execute('delete from grc20_tickers where block_height > %s;', (reorg_height,)) ## delete new tickers
  ## fetch mint events for reverting remaining_supply in other tickers
  cur.execute('''select event from grc20_events where event_type = %s and block_height > %s;''', (event_types["mint-inscribe"], reorg_height,))
  rows = cur.fetchall()
  tick_changes = {}
  code_changes = {}
  for row in rows:
    event = row[0]
    tick = event["tick"]
    code = event["code"]
    amount = int(event["amount"])
    if tick not in tick_changes:
      tick_changes[tick] = 0
    tick_changes[tick] += amount
    if tick not in code_changes:
      code_changes[tick] = {}
    if code not in code_changes[tick]:
      code_changes[tick][code] = 0
    code_changes[tick][code] += amount

  for tick in tick_changes:
    cur.execute('''update grc20_tickers set tick_remaining_supply = tick_remaining_supply + %s where tick = %s;''', (tick_changes[tick], tick))
  for tick in tick_changes:
    for code in code_changes[tick]:
      cur.execute('''update grc20_tickers set code_remaining_supply = code_remaining_supply + %s where tick = %s and code = %s;''', (amount, tick,code))
  cur.execute('delete from grc20_events where block_height > %s;', (reorg_height,)) ## delete new events
  cur.execute('delete from grc20_cumulative_event_hashes where block_height > %s;', (reorg_height,)) ## delete new bitmaps
  cur.execute("SELECT setval('grc20_cumulative_event_hashes_id_seq', max(id)) from grc20_cumulative_event_hashes;") ## reset id sequence
  cur.execute("SELECT setval('grc20_tickers_id_seq', max(id)) from grc20_tickers;") ## reset id sequence
  cur.execute("SELECT setval('grc20_events_id_seq', max(id)) from grc20_events;") ## reset id sequence
  cur.execute('delete from grc20_block_hashes where block_height > %s;', (reorg_height,)) ## delete new block hashes
  cur.execute("SELECT setval('grc20_block_hashes_id_seq', max(id)) from grc20_block_hashes;") ## reset id sequence
  cur.execute('commit;')
  reset_caches()

def check_if_there_is_residue_from_last_run():
  cur.execute('''select max(block_height) from grc20_block_hashes;''')
  row = cur.fetchone()
  current_block = None
  if row[0] is None: current_block = first_inscription_height
  else: current_block = row[0] + 1
  residue_found = False
  cur.execute('''select coalesce(max(block_height), -1) from grc20_events;''')
  if cur.rowcount != 0 and cur.fetchone()[0] >= current_block:
    residue_found = True
    print("residue on grc20_events")
  cur.execute('''select coalesce(max(block_height), -1) from grc20_tickers;''')
  if cur.rowcount != 0 and cur.fetchone()[0] >= current_block:
    residue_found = True
    print("residue on tickers")
  cur.execute('''select coalesce(max(block_height), -1) from grc20_cumulative_event_hashes;''')
  if cur.rowcount != 0 and cur.fetchone()[0] >= current_block:
    residue_found = True
    print("residue on cumulative hashes")
  if residue_found:
    print("There is residue from last run, rolling back to " + str(current_block - 1))
    reorg_fix(current_block - 1)
    print("Rolled back to " + str(current_block - 1))
    return

def check_if_there_is_residue_on_extra_tables_from_last_run():
  pass


cur.execute('select event_type_name, event_type_id from grc20_event_types;')
event_types = {}
for row in cur.fetchall():
  event_types[row[0]] = row[1]

event_types_rev = {}
for key in event_types:
  event_types_rev[event_types[key]] = key

sttm = time.time()
cur.execute('''select tick, code, max_tick_supply, max_code_supply,  tick_remaining_supply, code_remaining_supply, decimals from grc20_tickers;''')
ticks_ = cur.fetchall()
ticks = {}
for t in ticks_:
  if t[0] not in ticks:
    ticks[t[0]] = {}
  ticks[t[0]][t[1]] = [t[2], t[3], t[4], t[5], t[6]]
print("Ticks refreshed in " + str(time.time() - sttm) + " seconds")

def reindex_cumulative_hashes():
  global event_types_rev, ticks
  cur.execute('''delete from grc20_cumulative_event_hashes;''')
  cur.execute('''select min(block_height), max(block_height) from grc20_block_hashes;''')
  row = cur.fetchone()
  min_block = row[0]
  max_block = row[1]


  sttm = time.time()
  cur.execute('''select tick, code, max_tick_supply, max_code_supply,  tick_remaining_supply, code_remaining_supply, decimals from grc20_tickers;''')
  ticks_ = cur.fetchall()
  ticks = {}
  for t in ticks_:
    if t[0] not in ticks:
      ticks[t[0]] = {}
    ticks[t[0]][t[1]] = [t[2], t[3], t[4], t[5], t[6]]
  print("Ticks refreshed in " + str(time.time() - sttm) + " seconds")

  print("Reindexing cumulative hashes from " + str(min_block) + " to " + str(max_block))
  for block_height in range(min_block, max_block + 1):
    print("Reindexing block " + str(block_height))
    block_events_str = ""
    cur.execute('''select event, event_type, inscription_id from grc20_events where block_height = %s order by id asc;''', (block_height,))
    rows = cur.fetchall()
    for row in rows:
      event = row[0]
      event_type = event_types_rev[row[1]]
      inscription_id = row[2]
      block_events_str += get_event_str(event, event_type, inscription_id) + EVENT_SEPARATOR
    update_event_hashes(block_height)

cur.execute('select db_version from grc20_indexer_version;')
if cur.rowcount == 0:
  print("Indexer version not found, db needs to be recreated from scratch, please run reset_init.py")
  exit(1)
else:
  db_version = cur.fetchone()[0]
  if db_version != DB_VERSION:
    print("Indexer version mismatch!!")
    if db_version not in RECOVERABLE_DB_VERSIONS:
      print("This version (" + str(db_version) + ") cannot be fixed, please run reset_init.py")
      exit(1)
    else:
      print("This version (" + str(db_version) + ") can be fixed, fixing in 5 secs...")
      time.sleep(5)
      reindex_cumulative_hashes()
      cur.execute('alter table grc20_indexer_version add column if not exists db_version int4;') ## next versions will use DB_VERSION for DB check
      cur.execute('update grc20_indexer_version set indexer_version = %s, db_version = %s;', (INDEXER_VERSION, DB_VERSION,))
      print("Fixed.")

def try_to_report_with_retries(to_send):
  global report_url, report_retries
  for _ in range(0, report_retries):
    try:
      r = requests.post(report_url, json=to_send)
      if r.status_code == 200:
        print("Reported hashes to metaprotocol indexer indexer.")
        return
      else:
        print("Error while reporting hashes to metaprotocol indexer indexer, status code: " + str(r.status_code))
    except KeyboardInterrupt:
      raise KeyboardInterrupt
    except:
      print("Error while reporting hashes to metaprotocol indexer indexer, retrying...")
    time.sleep(1)
  print("Error while reporting hashes to metaprotocol indexer indexer, giving up.")

def report_hashes(block_height):
  global report_to_indexer
  if not report_to_indexer:
    print("Reporting to metaprotocol indexer is disabled.")
    return
  cur.execute('''select block_event_hash, cumulative_event_hash from grc20_cumulative_event_hashes where block_height = %s;''', (block_height,))
  row = cur.fetchone()
  block_event_hash = row[0]
  cumulative_event_hash = row[1]
  cur.execute('''select block_hash from grc20_block_hashes where block_height = %s;''', (block_height,))
  block_hash = cur.fetchone()[0]
  to_send = {
    "name": report_name,
    "type": "grc20",
    "node_type": "full_node",
    "network_type": network_type,
    "version": INDEXER_VERSION,
    "db_version": DB_VERSION,
    "event_hash_version": EVENT_HASH_VERSION,
    "block_height": block_height,
    "block_hash": block_hash,
    "block_event_hash": block_event_hash,
    "cumulative_event_hash": cumulative_event_hash
  }
  print("Sending hashes to metaprotocol indexer indexer...")
  try_to_report_with_retries(to_send)

def reorg_on_extra_tables(reorg_height):
  pass

def initial_index_of_extra_tables():
  pass


def index_extra_tables(block_height, block_hash):
  pass


def check_extra_tables():
  pass


check_if_there_is_residue_from_last_run()
if create_extra_tables:
  check_if_there_is_residue_on_extra_tables_from_last_run()
  print("checking extra tables")
  check_extra_tables()

last_report_height = 0
while True:
  check_if_there_is_residue_from_last_run()
  if create_extra_tables:
    check_if_there_is_residue_on_extra_tables_from_last_run()
  ## check if a new block is indexed
  cur_metaprotocol.execute('''SELECT coalesce(max(block_height), -1) as max_height from block_hashes;''')
  max_block_of_metaprotocol_db = cur_metaprotocol.fetchone()[0]
  cur.execute('''select max(block_height) from grc20_block_hashes;''')
  row = cur.fetchone()
  current_block = None
  if row[0] is None: current_block = first_inscription_height
  else: current_block = row[0] + 1
  if current_block > max_block_of_metaprotocol_db:
    print("Waiting for new blocks...")
    time.sleep(5)
    continue
  
  print("Processing block %s" % current_block)
  cur_metaprotocol.execute('select block_hash from block_hashes where block_height = %s;', (current_block,))
  current_block_hash = cur_metaprotocol.fetchone()[0]
  reorg_height = check_for_reorg()
  if reorg_height is not None:
    print("Rolling back to ", reorg_height)
    reorg_fix(reorg_height)
    print("Rolled back to " + str(reorg_height))
    continue
  try:
    index_block(current_block, current_block_hash)
    if create_extra_tables and max_block_of_metaprotocol_db - current_block < 10: ## only update extra tables at the end of sync
      print("checking extra tables")
      check_extra_tables()
    if max_block_of_metaprotocol_db - current_block < 10 or current_block - last_report_height > 100: ## do not report if there are more than 10 blocks to index
      report_hashes(current_block)
      last_report_height = current_block
  except KeyboardInterrupt:
    traceback.print_exc()
    if in_commit: ## rollback commit if any
      print("rolling back")
      cur.execute('''ROLLBACK;''')
      in_commit = False
    print("Exiting...")
    sys.exit(1)
  except:
    traceback.print_exc()
    if in_commit: ## rollback commit if any
      print("rolling back")
      cur.execute('''ROLLBACK;''')
      in_commit = False
    time.sleep(10)
