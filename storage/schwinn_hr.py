import asyncio
from bleak import BleakClient
import time
glbSchwinn = { 
    "name": "Schwinn", "address": "84:71:27:27:4A:44", 
    "CommandRecord":        "1717b3c0-9803-11e3-90e1-0002a5d5c51b", #write
    "AckRecord":            "35ddd0a0-9803-11e3-9a8b-0002a5d5c51b", #notify, read
    "DataRecord":           "4ed124e0-9803-11e3-b14c-0002a5d5c51b", #read
    "EventRecord":          "5c7d82a0-9803-11e3-8a6c-0002a5d5c51b", #notify
    "StreamingReadData0":   "6be8f580-9803-11e3-ab03-0002a5d5c51b", #notify
    "StreamingReadData1":   "a46a4a80-9803-11e3-8f3c-0002a5d5c51b", #notify
    "StreamingReadData2":   "b8066ec0-9803-11e3-8346-0002a5d5c51b", #notify
    "StreamingReadData3":   "d57cda20-9803-11e3-8426-0002a5d5c51b", #notify
    "StreamingWriteData0":  "ec865fc0-9803-11e3-8bf6-0002a5d5c51b", #write no response
    "DebugStatus":          "7241b880-a560-11e3-9f31-0002a5d5c51b"  #read
}
glbClient = None
glbLastHr = -1
glbSrdSeq0 = -1
glbCommandToAck = -1

async def AckRecordCb(sender, data):
    global glbClient
    if len(data) == 4 and data[1] == glbCommandToAck and data[2] == 0 and data[3] == 0:
        #print("AckRecordCb OK")
        dr = await glbClient.read_gatt_char(glbSchwinn['DataRecord'])
        print(f"DataRecord: {len(dr)}: {dr.hex('-')}")
    else:
        print(f"AckRecordCb NOT OK: {len(data)}: {data.hex('-')}")
        pass

def StreamingReadDataCb0(sender, data):
    global glbLastHr, glbSrdSeq0
    print(f"StreamingReadDataCb0: {len(data)}: {data.hex('-')}")
    if len(data) == 20:
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
    print(f"StreamingReadDataCb2: {len(data)}: {data.hex('-')}")

def StreamingReadDataCb3(sender, data):
    print(f"StreamingReadDataCb3: {len(data)}: {data.hex('-')}")

def EventCb(sender, data):
    if data[0] == 0x11 and data[1] == 0x20:
        pass #filter out cadence
    else:
        print(f"EventCb: {len(data)}: {data.hex('-')}")

glbCommandSeq = 1
def generateCommand(c):
    global glbCommandToAck, glbCommandSeq
    ret = bytearray(b'\x05\x03\x00\x00\x00')
    ret[1] = glbCommandSeq % 256
    ret[4] = c
    sum = 0
    for b in ret:
        sum += int(b)
    ret[2] = (256 - (sum % 256)) % 256
    glbCommandToAck = c
    glbCommandSeq = glbCommandSeq + 1
    return bytes(ret)

def generateCommandOneByteParam(c, t, p):
    global glbCommandToAck, glbCommandSeq
    ret = bytearray(b'\x07\x03\x00\x00\x00\x27\x00')
    ret[1] = glbCommandSeq % 256
    ret[4] = c
    ret[5] = t
    ret[6] = p
    sum = 0
    for b in ret:
        sum += int(b)
    ret[2] = (256 - (sum % 256)) % 256
    glbCommandToAck = c
    glbCommandSeq = glbCommandSeq + 1
    return bytes(ret)

async def main(address):
    global glbClient
    print(f"Starting {address['name']}...")
    async with BleakClient(address['address'], timeout = 150.0) as client:
        glbClient = client
        print(f"{address['name']} connected: {client.is_connected}")
        try:
            await client.start_notify(address['EventRecord'], EventCb) # 0x20: cadence, calories, resistance; 0x09: workout state change (start, pause, stop)
            await client.start_notify(address['AckRecord'], AckRecordCb)
            await client.start_notify(address['StreamingReadData0'], StreamingReadDataCb0) # [16]: heart rate
            await client.start_notify(address['StreamingReadData1'], StreamingReadDataCb1) #nothing interesting found here
            await client.start_notify(address['StreamingReadData2'], StreamingReadDataCb2)
            await client.start_notify(address['StreamingReadData3'], StreamingReadDataCb3)

            #known commands            
            #REQUEST_BLE_ACCESS=0x0b (may be omitted?)
            #await client.write_gatt_char(address['CommandRecord'], generateCommand(0x0b))
            #await asyncio.sleep(1)

            #GIVEUP_BLE_ACCESS=0x0c
            #GET_USER_DATA=0x18: [7, seq, sum, 0, 0x18, 0x28 /*USER_INDEX_DATA_TYPE*/, user]
            #GET_WORKOUT_DATA=0x19: [0x0a, seq, sum, 0, 0x19, 0x28 /*USER_INDEX_DATA_TYPE*/, user, /*WORKOUT_INDEX_DATA_TYPE*/, work, 0 ]
    
            #                            cmd
            #DataRecord: 32: 20-03-00-00-04-28-03-19-00-39-01-3c-05-00-5a-00-5c-04-5f-00-61-00-00-60-00-00-3d-00-00-3e-00-00
            #DataRecord:  9: 09-03-9b-00-09-28-03-22-03
            #DataRecord: 11: 0b-03-ce-00-0d-28-03-19-01-cf-03 #GET_STATUS
            #DataRecord: 46: 2e-03-b0-00-15-0c-2c-00-14-0f-52-00-00-0d-0e-4e-61-75-74-69-6c-75-73-2c-20-49-6e-63-00-0e-0f-53-43-48-57-49-4e-4e-20-31-37-30-2f-32-37-00 #GET_PRODUCT_DATA
            #DataRecord: 22: 16-03-58-00-17-24-04-25-1a-1f-1b-04-1b-08-20-00-06-02-0d-7a-01-00 #GET_SYSTEM_DATA
            #DataRecord: 29: 1d-03-bb-00-60-c9-01-cb-00-00-cb-2c-00-cb-00-10-cb-00-01-cd-ff-ff-ff-ff-cd-ff-ff-ff-ff
            #DataRecord: 10: 0a-03-49-00-62-cd-04-d6-01-a0
            #DataRecord: 10: 0a-03-52-00-66-cd-b4-be-fb-01
            #DataRecord:  8: 08-03-c3-00-67-cb-00-00
            #DataRecord: 10: 0a-03-35-00-70-cd-08-d8-01-a0

            #print(f"Heart 62 3-sec test begin")
            #await client.write_gatt_char(address['CommandRecord'], generateCommand(0x62)) #start streaming 0 for heart rate (and streaming 1 also)
            #await asyncio.sleep(3)
            #print(f"Heart 62 3-sec test end")
            #await asyncio.sleep(3)
            #await client.write_gatt_char(address['CommandRecord'], generateCommand(0x1e)) #stop all streams
            #print(f"Stop streaming 0-1")

            #print(f"Heart rate 3-sec test begin")
            #await client.write_gatt_char(address['CommandRecord'], generateCommand(0x1f)) #start streaming 0 for heart rate (and streaming 1 also)
            #await asyncio.sleep(3)
            #print(f"Heart rate 3-sec test end")
            #await asyncio.sleep(3)
            #await client.write_gatt_char(address['CommandRecord'], generateCommand(0x1e)) #stop all streams
            #print(f"Stop streaming 0-1")
            #                dt    dt v  dt v  dt v  v  dt v  dt v  ??
            #77-20-3a-65-00-1f-28-03-19-00-39-01-3c-75-00-5a-00-5c-01-5f
            #78-20-3b-65-00-1f-28-03-19-00-39-01-3c-75-00-5a-00-5c-01-5f (0x14)
            #c1    c2          usr   prg   ??    work_tim hr    rs    fin
            #7b-20-01-12-00-1f-28-03-19-00-39-01-3c-00-00-5a-00-5c-02-5f
            #a3-20-29-4a-00-1f-28-03-19-00-39-01-3c-02-00-5a-00-5c-04-5f
            #50-20-81-73-00-1f-28-03-19-00-39-01-3c-5e-00-5a-00-5c-04-5f
            #xx xx xx xx 00 1f 5c 05 5f - не проконало поставить 5c(сопр)=05
            print(f"Heart Write0 test begin")
            #await client.write_gatt_char(address['CommandRecord'], generateCommand(0x1f)) #start streaming 0 for heart rate (and streaming 1 also)
            for c in range(1, 255):
                arr = bytearray(b'\xf8\x20\x04\x60\x5c\x01\x5f')
                arr[0] = c
                arr[1] = 0x20
                arr[2] = c
                arr[3] = c
                await client.write_gatt_char(address['StreamingWriteData0'], arr)
                await asyncio.sleep(0.1)
            #await client.write_gatt_char(address['CommandRecord'], generateCommand(0x1e)) #stop all streams
            print(f"Stop streaming")

            #print(f"Start 3-sec streaming test 0-1-2-3 running byte")
            #await client.write_gatt_char(address['CommandRecord'], generateCommand(0x27))
            #await asyncio.sleep(3)
            #await client.write_gatt_char(address['CommandRecord'], generateCommand(0x1e)) #stop all streams
            #print(f"Stop streaming 2-3")

            #for c in range(1, 255):
            #    if c in [4,9,0xb,0xc,0xd,0x15,0x17,0x1e,0x1f,0x27,0x60,0x62,0x66,0x67,0x70]:
            #        continue
            #    print(f"cmd={c}")
            #    for t in range(120):
            #        print(f"t={t}")
            #        await client.write_gatt_char(address['CommandRecord'], generateCommandOneByteParam(c, t, 20))
            #        await asyncio.sleep(0.1)

            await asyncio.sleep(60.0 * 10)
            await client.stop_notify(address['StreamingReadData3'])
            await client.stop_notify(address['StreamingReadData2'])
            await client.stop_notify(address['StreamingReadData1'])
            await client.stop_notify(address['StreamingReadData0'])
            await client.stop_notify(address['AckRecord'])
        except Exception as e:
            print(e)        
    print(f"Stopped {address['name']}")

if __name__ == "__main__":
    asyncio.run(main(glbSchwinn))
