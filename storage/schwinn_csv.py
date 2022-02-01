def calc_energy(res, cadence):    
    if (res == 1) and (cadence > 14): #integral delta 0.76%
        return (cadence - 14) * 49 / 87
    if (res == 2) and (cadence > 18): #integral delta 0.7%
        return (cadence - 18) * 80 / 95
    if (res == 3) and (cadence > 17): #integral delta 0.7%
        return (cadence - 17) * 104 / 103
    if (res == 4) and (cadence > 18): #integral delta 2.6% (сглажены всплески assiom)
        return (cadence - 18) * 99 / 87
    if (res == 5) and (cadence > 21): #integral delta 0.03%
        return (cadence - 21) * 137 / 89
    if (res == 6) and (cadence > 20): #integral delta 0.94%
        return (cadence - 20) * 140 / 82
    if (res == 7) and (cadence > 22): #integral delta 0.46%
        return (cadence - 22) * 166 / 83
    if (res == 8) and (cadence > 22): #integral delta 0.03%
        return (cadence - 22) * 178 / 79
    if (res == 9) and (cadence > 23): #integral delta 0.78%
        return (cadence - 23) * 199 / 79
    if (res == 10) and (cadence > 26): #integral delta 0.62%
        return (cadence - 26) * 287 / 96
    if (res == 11) and (cadence > 22): #integral delta 0.46%
        return (cadence - 22) * 285 / 98
    if (res == 12) and (cadence > 21): #integral delta 0.58%
        return (cadence - 21) * 265 / 79
    if (res == 13) and (cadence > 20): #integral delta 1.25% (сглажены всплески assiom)
        return (cadence - 20) * 312 / 85
    if (res == 14) and (cadence > 22): #integral delta 1.4%
        return (cadence - 22) * 340 / 88
    if (res == 15) and (cadence > 20): #integral delta 1.8%
        return (cadence - 20) * 343 / 80
    if (res == 16) and (cadence > 21): #integral delta 0.21%
        return (cadence - 21) * 315 / 69
    if (res == 17) and (cadence > 20): #integral delta 1.3%
        return (cadence - 20) * 325 / 70
    if (res == 18) and (cadence > 18): #integral delta 1.8%
        return (cadence - 18) * 260 / 52
    if (res == 19) and (cadence > 21): #integral delta 2%
        return (cadence - 21) * 340 / 64
    if (res == 20) and (cadence > 17): #integral delta 1.8%
        return (cadence - 17) * 315 / 63

    if (res == 24) and (cadence > 15): #integral delta 1.7%
        return (cadence - 15) * 295 / 47
    if (res == 25) and (cadence > 17): #integral delta 0.96%
        return (cadence - 17) * 535 / 73
    return 0

last_dev_time = 0
last_crank = 0.0
#last_calories = 0
stime = 0
not_first = False
last_dtime = 1.0
#name = '1schwinn_1642907272137'
#name = '2schwinn_1642911335080'
#name = '25schwinn_1642914463998'
#name = '12schwinn_1642916907218'
#name = '3schwinn_1642920003596'
#name = '4schwinn_1642922109948'
#name = '5schwinn_1642922447079'
#name = '6schwinn_1642922704592'
name = '7schwinn_1642923059928'
with open(f'{name}_full.csv', "w") as ftx:
    ftx.write("stime;dtime;cadence;resistance;energy;integr\n")
    with open(f'{name}.bin', "rb") as frx:
        while frx:
            data = frx.read(17)
            if len(data) == 0:
                break
            if data[3] != 0: #усреднение
                continue
            dev_time = data[8]+256*data[9]
            cor_time = dev_time
            crank = (data[3]+256*data[4]+65536*data[5]) / 256.0
            while cor_time < last_dev_time:
                cor_time += 65536
            dtime = (cor_time - last_dev_time) / 1024.0
            if dtime > 2.0: # бывает мусор: 11 20 00 60 18 55 00 00 2F BF 40 65 CB 0A 00 00 07 -> 11 20 00 80 18 55 B9 99 1B 00 E0 47 CD 0A 00 00 07
                dtime = last_dtime #а вообще лучше по времени системы еще проверять
            last_dtime = dtime
            cadence = (crank - last_crank) * 60.0 / dtime
            last_crank = crank
            last_dev_time = cor_time
            #calories = data[10]+256*data[11]+65536*data[12]+16777216*data[13]
            #dcalories = calories - last_calories
            #last_calories = calories
            if not_first: #dcalories != calories:
                energy = calc_energy(data[16], cadence)
                stime += dtime
                #            stime;  dtime;  cadence;  resistance
                ftx.write(f"{stime};{dtime};{cadence};{data[16]};{energy};{energy*dtime}\n")
            not_first = True