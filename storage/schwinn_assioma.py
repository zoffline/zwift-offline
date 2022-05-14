import asyncio
from bleak import BleakClient
import time

def current_milli_time():
    return time.time_ns() // 1_000_000

cb = 0
start = current_milli_time()
with open(f'schwinn_{start}.csv', "w") as f:
    f.write("time,dev_time,cor_time,crank,calories,resistance,assioma_power\n")
with open(f'assioma_{start}.csv', "w") as f:
    #f.write("time,dev_time,cor_time,crank,power,balance\n")
    f.write("time,power\n")

last_dev_time = 0
last_crank = 0
last_assioma_power = 0
def schwinn_callback(sender, data):
    global cb, start, last_dev_time, last_crank, last_assioma_power
    curr = current_milli_time()
    if (len(data) != 17) or (data[0] != 17):
        return
    cb |= 1
    if cb == 3:
        with open(f'schwinn_{start}.bin', "ab") as f:
            f.write(data)
        dev_time = data[8]+256*data[9]
        cor_time = dev_time
        crank = data[4]+256*data[5]
        while cor_time < last_dev_time:
            cor_time += 65536
        if last_crank == crank:
            return # прореживаем
        print(f"S.{sender}: {data}") #b'\x11 \x00 yF\x00\x00\x1dGd\xbd\x15\x00\x00\x00\x04'
        last_crank = crank
        last_dev_time = cor_time
        with open(f'schwinn_{start}.csv', "a") as f:
            #          time,        dev_time,  cor_time,  crank,  calories,                                                resistance
            f.write(f"{curr-start},{dev_time},{cor_time},{crank},{data[10]+256*data[11]+65536*data[12]+16777216*data[13]},{data[16]},{last_assioma_power}\n")
#00 - 0x11 - размер
#01 - 0x20 - тип пакета?
#02 - 0x00 - тип пакета?
#03 - 1/8 оборотов
#04-05 LSB к-во оборотов
#06 ?
#07 ? какое-то битовое поле, не пульс!
#08-09 LSB к-во 1024-х секунды тренировки
#10 ? младшая часть калорий
#11-15 LSB какой-то еще счетчик, быстрее растет под нагрузкой - не калории ли
#16 Уровень сложности

def assioma_callback(sender, data):
    global cb, start, last_assioma_power
    curr = current_milli_time()
    if (len(data) != 9) or (data[0] != 0x23): #b'#\x00\x00\x00dN\x00W\x98'
        return
    cb |= 1
    if cb == 3:
        with open(f'assioma_{start}.bin', "ab") as f:
            f.write(data)
        last_assioma_power = data[2]+256*data[3]
        print(f"A: {last_assioma_power}")
        with open(f'assioma_{start}.csv', "a") as f:
            #          time,        dev_time,             crank,                power,                balance
            #f.write(f"{curr-start},{data[7]+256*data[8]},{data[5]+256*data[6]},{data[2]+256*data[3]},{data[4]}\n")
            #          time,        power
            f.write(f"{curr-start},{last_assioma_power}\n")

def schwinn_my_callback(sender, data):
    global cb, start, last_assioma_power
    curr = current_milli_time()
    #if (len(data) != 9) or (data[0] != 0x23): #b'E\x02E\x00\x1f\x00\x02'
    #    return
    cb |= 2
    if cb == 3:
        with open(f'schwinn_my{start}.bin', "ab") as f:
            f.write(data)
        my_power = data[4]+256*data[5]
        print(f"M: {my_power}")
        with open(f'schwinn_my{start}.csv', "a") as f:
            #          time,        dev_time,             crank,                power,                balance
            #f.write(f"{curr-start},{data[7]+256*data[8]},{data[5]+256*data[6]},{data[2]+256*data[3]},{data[4]}\n")
            #          time,        power
            f.write(f"{curr-start},{my_power},{last_assioma_power}\n")

async def connect_to_device(address):
    print(f"Starting {address['name']}...")
    async with BleakClient(address['address'], timeout = 150.0) as client:
        print(f"{address['name']} connected: {client.is_connected}")
        try:
            await client.start_notify(address['char'], address['callback'])
            await asyncio.sleep(60.0 * 25)
            await client.stop_notify(address['char'])
        except Exception as e:
            print(e)        
    print(f"Stopped {address['name']}")

async def main(addresses):
    await asyncio.gather(*(connect_to_device(address) for address in addresses))


if __name__ == "__main__":
    asyncio.run(
        main(
            [
                {"name": "Assioma", "address": "E7:01:AD:C7:2A:B7", "char": "00002a63-0000-1000-8000-00805F9B34FB", "callback": assioma_callback },
                #{"name": "Schwinn", "address": "84:71:27:27:4A:44", "char": "5c7d82a0-9803-11e3-8a6c-0002a5d5c51b", "callback": schwinn_callback },
                {"name": "SchwinnMy", "address": "30:AE:A4:8B:97:8A", "char": "00002ad2-0000-1000-8000-00805F9B34FB", "callback": schwinn_my_callback },
            ]
        )
    )
