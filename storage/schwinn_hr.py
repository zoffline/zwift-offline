import asyncio
from bleak import BleakClient
import time

glbClient = None

async def AckRecordCb(sender, data):
    global glbClient
    if data[0] == 3 and data[1] == 0x1f and data[2] == 0 and data[3] == 0:
        print("AckRecordCb OK")
        dr = await glbClient.read_gatt_char('4ed124e0-9803-11e3-b14c-0002a5d5c51b') #DataRecord
        print(f"DataRecord: {len(dr)}: {dr.hex('-')}")
    else:
        print(f"AckRecordCb NOT OK: {len(data)}: {data.hex('-')}")

def AckRecordCbNa(sender, data):
    global glbClient
    if data[0] == 3 and data[1] == 0x1f and data[2] == 0 and data[3] == 0:
        print("AckRecordCb OK")
    else:
        print(f"AckRecordCb NOT OK: {len(data)}: {data.hex('-')}")

glbLastHr = -1
glbSrdSeq0 = -1
def StreamingReadDataCb0(sender, data):
    global glbLastHr, glbSrdSeq0
    if len(data) != 20:
        print(f"StreamingReadDataCb0: len expected: 20, got {len(data)}: {data.hex('-')}")
    else:
        if glbSrdSeq0 == -1:
            glbSrdSeq0 = data[0] - 1
        if glbSrdSeq0 > data[0]:
            print(f"StreamingReadDataCb0 seq expected > {glbSrdSeq0}, got: {data.hex('-')}")
        else:
            if glbLastHr != data[16]:
                glbLastHr = data[16]
                print(f"HR = {glbLastHr}")
        glbSrdSeq0 = (data[0] + 1) % 256

def StreamingReadDataCb1(sender, data):
    print(f"StreamingReadDataCb1: {len(data)}: {data.hex('-')}")

def StreamingReadDataCb2(sender, data):
    print(f"StreamingReadDataCb0: {len(data)}: {data.hex('-')}")

def StreamingReadDataCb3(sender, data):
    print(f"StreamingReadDataCb3: {len(data)}: {data.hex('-')}")

async def connect_to_device(address):
    global glbClient
    print(f"Starting {address['name']}...")
    async with BleakClient(address['address'], timeout = 150.0) as client:
        glbClient = client
        print(f"{address['name']} connected: {client.is_connected}")
        try:
            await client.start_notify(address['AckRecord'], AckRecordCb)
            await client.start_notify(address['StreamingReadData0'], StreamingReadDataCb0)
            #await client.start_notify(address['StreamingReadData1'], StreamingReadDataCb1)
            #await client.start_notify(address['StreamingReadData2'], StreamingReadDataCb2)
            #await client.start_notify(address['StreamingReadData3'], StreamingReadDataCb3)
            await client.write_gatt_char(address['CommandRecord'], b'\x05\x03\xd9\x00\x1f') #start streaming 0 & 1
            await asyncio.sleep(60.0 * 10)
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
                {"name": "Schwinn", "address": "84:71:27:27:4A:44", 
                    "CommandRecord":        "1717b3c0-9803-11e3-90e1-0002a5d5c51b", #write
                    "AckRecord":            "35ddd0a0-9803-11e3-9a8b-0002a5d5c51b", #notify, read
                    "DataRecord":           "4ed124e0-9803-11e3-b14c-0002a5d5c51b", #read
                    #"EventRecord":          "5c7d82a0-9803-11e3-8a6c-0002a5d5c51b", #notify
                    "StreamingReadData0":   "6be8f580-9803-11e3-ab03-0002a5d5c51b", #notify
                    "StreamingReadData1":   "a46a4a80-9803-11e3-8f3c-0002a5d5c51b", #notify
                    "StreamingReadData2":   "b8066ec0-9803-11e3-8346-0002a5d5c51b", #notify
                    "StreamingReadData3":   "d57cda20-9803-11e3-8426-0002a5d5c51b", #notify
                    #"StreamingWriteData0":  "ec865fc0-9803-11e3-8bf6-0002a5d5c51b", #write no response
                    #"DebugStatus":          "7241b880-a560-11e3-9f31-0002a5d5c51b"  #read
                },
            ]
        )
    )
