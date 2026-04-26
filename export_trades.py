import sqlite3 as s

c = s.connect('data/tradecraftx.db')
rows = c.execute('SELECT COUNT(*) FROM user_trades WHERE broker=?', ['upstox']).fetchone()
print(f'UPSTOX_COUNT={rows[0]}')

trades = c.execute('''
    SELECT trade_date, symbol, side, quantity, price, trade_id 
    FROM user_trades 
    WHERE broker=? 
    ORDER BY trade_date DESC
''', ['upstox']).fetchall()

fn = 'data/order_history_upstox_all.csv'
with open(fn, 'w', encoding='utf-8') as f:
    f.write('trade_date,symbol,side,quantity,price,trade_id\n')
    for t in trades:
        f.write(f'{t[0]},{t[1]},{t[2]},{t[3]},{t[4]},{t[5]}\n')

print(f'WROTE {len(trades)} rows to {fn}')