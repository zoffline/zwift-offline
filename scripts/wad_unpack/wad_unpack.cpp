#include <iostream>
#include <cstdio>
#include <filesystem>
#include <windows.h>
#include <map>
#include "WCX-SDK-master\src\wcxhead.h"

const uint8_t* g_cypher = (const uint8_t*)"5.QX2Y0view < MAX_VIEWS";
const uint32_t g_signatureTable[256] = {
    0, 0x77073096, 0xEE0E612C, 0x990951BA, 0x76DC419, 0x706AF48F,
    0xE963A535, 0x9E6495A3, 0xEDB8832, 0x79DCB8A4, 0xE0D5E91E,
    0x97D2D988, 0x9B64C2B, 0x7EB17CBD, 0xE7B82D07, 0x90BF1D91,
    0x1DB71064, 0x6AB020F2, 0xF3B97148, 0x84BE41DE, 0x1ADAD47D,
    0x6DDDE4EB, 0xF4D4B551, 0x83D385C7, 0x136C9856, 0x646BA8C0,
    0xFD62F97A, 0x8A65C9EC, 0x14015C4F, 0x63066CD9, 0xFA0F3D63,
    0x8D080DF5, 0x3B6E20C8, 0x4C69105E, 0xD56041E4, 0xA2677172,
    0x3C03E4D1, 0x4B04D447, 0xD20D85FD, 0xA50AB56B, 0x35B5A8FA,
    0x42B2986C, 0xDBBBC9D6, 0xACBCF940, 0x32D86CE3, 0x45DF5C75,
    0xDCD60DCF, 0xABD13D59, 0x26D930AC, 0x51DE003A, 0xC8D75180,
    0xBFD06116, 0x21B4F4B5, 0x56B3C423, 0xCFBA9599, 0xB8BDA50F,
    0x2802B89E, 0x5F058808, 0xC60CD9B2, 0xB10BE924, 0x2F6F7C87,
    0x58684C11, 0xC1611DAB, 0xB6662D3D, 0x76DC4190, 0x1DB7106,
    0x98D220BC, 0xEFD5102A, 0x71B18589, 0x6B6B51F, 0x9FBFE4A5,
    0xE8B8D433, 0x7807C9A2, 0xF00F934, 0x9609A88E, 0xE10E9818,
    0x7F6A0DBB, 0x86D3D2D, 0x91646C97, 0xE6635C01, 0x6B6B51F4,
    0x1C6C6162, 0x856530D8, 0xF262004E, 0x6C0695ED, 0x1B01A57B,
    0x8208F4C1, 0xF50FC457, 0x65B0D9C6, 0x12B7E950, 0x8BBEB8EA,
    0xFCB9887C, 0x62DD1DDF, 0x15DA2D49, 0x8CD37CF3, 0xFBD44C65,
    0x4DB26158, 0x3AB551CE, 0xA3BC0074, 0xD4BB30E2, 0x4ADFA541,
    0x3DD895D7, 0xA4D1C46D, 0xD3D6F4FB, 0x4369E96A, 0x346ED9FC,
    0xAD678846, 0xDA60B8D0, 0x44042D73, 0x33031DE5, 0xAA0A4C5F,
    0xDD0D7CC9, 0x5005713C, 0x270241AA, 0xBE0B1010, 0xC90C2086,
    0x5768B525, 0x206F85B3, 0xB966D409, 0xCE61E49F, 0x5EDEF90E,
    0x29D9C998, 0xB0D09822, 0xC7D7A8B4, 0x59B33D17, 0x2EB40D81,
    0xB7BD5C3B, 0xC0BA6CAD, 0xEDB88320, 0x9ABFB3B6, 0x3B6E20C,
    0x74B1D29A, 0xEAD54739, 0x9DD277AF, 0x4DB2615, 0x73DC1683,
    0xE3630B12, 0x94643B84, 0xD6D6A3E, 0x7A6A5AA8, 0xE40ECF0B,
    0x9309FF9D, 0xA00AE27, 0x7D079EB1, 0xF00F9344, 0x8708A3D2,
    0x1E01F268, 0x6906C2FE, 0xF762575D, 0x806567CB, 0x196C3671,
    0x6E6B06E7, 0xFED41B76, 0x89D32BE0, 0x10DA7A5A, 0x67DD4ACC,
    0xF9B9DF6F, 0x8EBEEFF9, 0x17B7BE43, 0x60B08ED5, 0xD6D6A3E8,
    0xA1D1937E, 0x38D8C2C4, 0x4FDFF252, 0xD1BB67F1, 0xA6BC5767,
    0x3FB506DD, 0x48B2364B, 0xD80D2BDA, 0xAF0A1B4C, 0x36034AF6,
    0x41047A60, 0xDF60EFC3, 0xA867DF55, 0x316E8EEF, 0x4669BE79,
    0xCB61B38C, 0xBC66831A, 0x256FD2A0, 0x5268E236, 0xCC0C7795,
    0xBB0B4703, 0x220216B9, 0x5505262F, 0xC5BA3BBE, 0xB2BD0B28,
    0x2BB45A92, 0x5CB36A04, 0xC2D7FFA7, 0xB5D0CF31, 0x2CD99E8B,
    0x5BDEAE1D, 0x9B64C2B0, 0xEC63F226, 0x756AA39C, 0x26D930A,
    0x9C0906A9, 0xEB0E363F, 0x72076785, 0x5005713, 0x95BF4A82,
    0xE2B87A14, 0x7BB12BAE, 0xCB61B38, 0x92D28E9B, 0xE5D5BE0D,
    0x7CDCEFB7, 0xBDBDF21, 0x86D3D2D4, 0xF1D4E242, 0x68DDB3F8,
    0x1FDA836E, 0x81BE16CD, 0xF6B9265B, 0x6FB077E1, 0x18B74777,
    0x88085AE6, 0xFF0F6A70, 0x66063BCA, 0x11010B5C, 0x8F659EFF,
    0xF862AE69, 0x616BFFD3, 0x166CCF45, 0xA00AE278, 0xD70DD2EE,
    0x4E048354, 0x3903B3C2, 0xA7672661, 0xD06016F7, 0x4969474D,
    0x3E6E77DB, 0xAED16A4A, 0xD9D65ADC, 0x40DF0B66, 0x37D83BF0,
    0xA9BCAE53, 0xDEBB9EC5, 0x47B2CF7F, 0x30B5FFE9, 0xBDBDF21C,
    0xCABAC28A, 0x53B39330, 0x24B4A3A6, 0xBAD03605, 0xCDD70693,
    0x54DE5729, 0x23D967BF, 0xB3667A2E, 0xC4614AB8, 0x5D681B02,
    0x2A6F2B94, 0xB40BBE37, 0xC30C8EA1, 0x5A05DF1B, 0x2D02EF8D
};

struct WadUnpacker {
    int g_ret = 0;
    bool g_bDumpMode;
    tProcessDataProc m_wcxProcess = nullptr;
    operator int() const { return g_ret; }
    WadUnpacker(char* fileName, bool bDumpMode = true) {
        g_bDumpMode = bDumpMode;
        m_curPosition = m_list.cbegin();
        auto err = fopen_s(&g_fwad, fileName, "rb");
        if (err != 0 || g_fwad == nullptr) {
            if(bDumpMode) std::cerr << "wad_unpack error: cannot open '" << fileName << "' for read, error: " << err << std::endl;
            g_ret = -2;
            return;
        }
        WAD_HEADER wad_hdr = {};
        if (sizeof(wad_hdr) == fread_s(&wad_hdr, sizeof(wad_hdr), 1, sizeof(wad_hdr), g_fwad)) {
            if (wad_hdr.m_fileSignature[0] == 'Z' && wad_hdr.m_fileSignature[1] == 'W' &&
                wad_hdr.m_fileSignature[2] == 'F' && wad_hdr.m_fileSignature[3] == '!') {
                if (wad_hdr.m_version == 0x0B) {
                    uint32_t decomp_buf_sz = ((wad_hdr.m_decompressed_size + 263) & 0xFFFFFFF8) + 0x100020;
                    m_decomp_buf = (uint8_t*)calloc(decomp_buf_sz, 1);
                    if (m_decomp_buf != nullptr) {
                        uint8_t* pDecompressPtr = (uint8_t*)((uint64_t)(m_decomp_buf + wad_hdr.m_decompressed_size + 256 - wad_hdr.m_compressed_size + 0x100000) & 0xFFFFFFFFFFFFFF80LL);
                        memcpy(m_decomp_buf, &wad_hdr, sizeof(wad_hdr));
                        g_compr_bytes_remain = wad_hdr.m_compressed_size;
                        g_compr_bytes = wad_hdr.m_compressed_size;
                        uint32_t bytesToRead = 0, new_compr_bytes_remain = 0;
                        if (wad_hdr.m_compressed_size) {
                            uint8_t* pDecompressEnd = m_decomp_buf + decomp_buf_sz;
                            if (wad_hdr.m_compressed_size >> 19)
                                bytesToRead = 0x80000LL;
                            else
                                bytesToRead = wad_hdr.m_compressed_size;
                            if (wad_hdr.m_compressed_size >> 19)
                                new_compr_bytes_remain = wad_hdr.m_compressed_size - 0x80000;
                            g_compr_bytes_remain = new_compr_bytes_remain;
                            if (&pDecompressPtr[bytesToRead] > pDecompressEnd) {
                                g_ret = -9;
                                if (bDumpMode) std::cerr << "wad_unpack assert: pDecompressPtr + bytesToRead <= pDecompressEnd\n";
                                return;
                            }
                            if (bytesToRead != fread_s(pDecompressPtr, bytesToRead, 1, bytesToRead, g_fwad)) {
                                g_ret = -10;
                                if (bDumpMode) std::cerr << "wad_unpack error: could not read initial block\n";
                                return;
                            }
                            if (g_compr_bytes_remain) {
                                bytesToRead = (g_compr_bytes_remain >> 19) ? 0x80000 : ((g_compr_bytes_remain + 7) & 0xFFFFFFF8);
                                g_compr_bytes_remain = (g_compr_bytes_remain >> 19) ? (g_compr_bytes_remain - 0x80000) : 0;
                                if (bytesToRead != fread_s(pDecompressPtr + 0x80000, bytesToRead, 1, bytesToRead, g_fwad)) {
                                    g_ret = -11;
                                    if (bDumpMode) std::cerr << "wad_unpack error: could not read second block\n";
                                    return;
                                }
                            }
                        }
                        uint32_t signature = 0;
                        uint32_t resultLength = TJZIP_Decompress(
                            pDecompressPtr,
                            m_decomp_buf + sizeof(wad_hdr),
                            wad_hdr.m_compressed_size,
                            &signature,
                            pDecompressPtr + 0x80000);
                        WAD_HEADER* wh = (WAD_HEADER*)m_decomp_buf;
                        if (resultLength == wh->m_decompressed_size) {
                            if (wh->m_signature != signature) {
                                g_ret = -8;
                                if (bDumpMode) std::cerr << "\nwad_unpack error: Wad Signature failure\n";
                            }
                            WAD_OffsetsToPointers(wh);
                            m_curPosition = m_list.cbegin();
                        }
                        else {
                            g_ret = -7;
                            if (bDumpMode) std::cerr << "\nwad_unpack error: Decompressed length error: resulting length = " << resultLength << ". Expected length = " <<
                                wh->m_decompressed_size << std::endl;
                        }
                    }
                    else {
                        g_ret = -6;
                        if (bDumpMode) std::cerr << "wad_unpack error: no memory, we need: " << decomp_buf_sz << std::endl;
                    }
                }
                else {
                    g_ret = -5;
                    if (bDumpMode) std::cerr << "wad_unpack error: unexpected wad file version(we need 11): " << wad_hdr.m_version << std::endl;
                }
            }
            else {
                g_ret = -4;
                if (bDumpMode) std::cerr << "wad_unpack error: unexpected wad file signature\n";
            }
        }
        else {
            g_ret = -3;
            if (bDumpMode) std::cerr << "wad_unpack error: unexpected eof while reading wad header\n";
        }
    }
    ~WadUnpacker() {
        if (g_fwad) fclose(g_fwad);
        if (m_decomp_buf) free(m_decomp_buf);
    }
    FILE* g_fwad = nullptr;
    uint8_t* m_decomp_buf = nullptr;
    uint32_t g_compr_bytes = 1, g_compr_bytes_remain = 0;
    uint8_t* g_pCallbackAt = nullptr;

    void EncryptDecryptWadString(uint8_t* str, uint32_t length)
    {
        __int64 v2;
        __int64 v3;
        __int64 v4;
        uint32_t v5;
        uint32_t v7;
        __int64 v8;
        int v9;
        int v10;
        int v11;
        int v12;
        const uint8_t* v13;
        int v14;
        v2 = uint32_t(length - 1);
        if (length >= 1) {
            v3 = v2 + 1;
            if (uint64_t(v2 + 1) <= 1) {
                v4 = 0;
            LABEL_7:
                v12 = int(length - v4);
                v4 = (uint32_t)v4;
                v13 = &g_cypher[(uint32_t)v4];
                do {
                    v14 = ((uint8_t)v13[-7 * (v4 / 7)] + 26 * (v12 / 26) - v12 - 65) ^ (uint8_t)*str;
                    --v12;
                    ++v13;
                    *str++ = v14;
                    ++v4;
                } while (v12);
                return;
            }
            v4 = v3 & 0x1FFFFFFFELL;
            v5 = 0;
            uint8_t* v6a = str + 1;
            v7 = 1;
            str += v3 & 0x1FFFFFFFELL;
            v8 = v3 & 0x1FFFFFFFELL;
            v9 = length;
            do {
                v10 = 26 * (v9 / 26) - v9;
                v11 = ((uint8_t)g_cypher[v7 % 7] + 1 - v9 + 26 * ((v9 - 1) / 26) - 65) ^ (uint8_t)*v6a;
                v9 -= 2;
                v8 -= 2LL;
                v7 += 2;
                *(v6a - 1) ^= g_cypher[v5 % 7] + v10 - 65;
                *v6a = v11;
                v6a += 2;
                v5 += 2;
            } while (v8);
            if (v3 != v4)
                goto LABEL_7;
        }
    }
    struct WAD_FILE_HEADER {
        uint32_t f0;
        char m_filePath[96];
        uint32_t m_assetType, m_fileLength, m_unk;
        WAD_FILE_HEADER* m_nextFile, * m_nextFileSameAsset;
        uint64_t f80;
        void* f88_visited;
        int32_t m_crypted, f94;
        uint64_t f98, fA0, fA8, fB0, fB8;
        uint8_t m_firstChar;
        void dump(bool bDumpMode, std::map<std::string, WAD_FILE_HEADER*> *pList) {
            std::cout << m_filePath;
            if (f88_visited == this) {
                if(bDumpMode) std::cout << " skipped (already saved)\n";
            }
            else {
                char path[97] = {};
                int lastDelimiter = -1;
                for (int i = 0; i < 96; i++) {
                    char cin = m_filePath[i];
                    if (cin == 0) break;
                    switch (cin) {
                    case '/': case '\\':
                        lastDelimiter = i;
                        path[i] = '\\';
                        break;
                    case '"': case '*': case '<': case '>': case '?': case '|': case ':':
                        path[i] = '#';
                        break;
                    default:
                        path[i] = cin;
                        break;
                    }
                }
                if (bDumpMode) {
                    if (lastDelimiter != -1) {
                        path[lastDelimiter] = 0;
                        if (!std::filesystem::is_directory(path) && !std::filesystem::create_directories(path)) {
                            std::cout << " failed to create dirs, quit\n";
                            exit(-12);
                        }
                        path[lastDelimiter] = '\\';
                    }
                    FILE* f = nullptr;
                    fopen_s(&f, path, "wb");
                    if (f == nullptr || m_fileLength != fwrite(&m_firstChar, 1, m_fileLength, f)) {
                        std::cout << " failed to write, quit\n";
                        exit(-13);
                    }
                    std::cout << ' ' << m_fileLength << " bytes saved OK\n";
                    fclose(f);
                } else {
                    (*pList)[path] = this;
                }
                f88_visited = this;
            }
        }
    };
    struct WAD_HEADER {
        char m_fileSignature[4];
        uint32_t arr25[25];
        WAD_FILE_HEADER* m_assets[17];
        uint32_t m_signature;
        uint32_t m_version;
        uint32_t m_decompressed_size;
        uint32_t m_compressed_size;
    };
    uint8_t* WAD_DecompCallback(uint8_t* pDest) {
        uint32_t new_compr_bytes_remain;
        uint32_t readNow;
        if (g_compr_bytes_remain) {
            new_compr_bytes_remain = g_compr_bytes_remain - 0x80000;
            if (!(g_compr_bytes_remain >> 19))
                new_compr_bytes_remain = 0;
            readNow = (g_compr_bytes_remain >> 19) ? 0x80000 : g_compr_bytes_remain;
            g_compr_bytes_remain = new_compr_bytes_remain;
            int percent = (100 - 100 * new_compr_bytes_remain / g_compr_bytes);
            if(g_bDumpMode) std::cout << percent << "%\r";
            if(m_wcxProcess && m_wcxProcess(nullptr, -percent) == 0) return 0LL;
            if (readNow) {
                if (readNow != fread_s(pDest + 0x80000, readNow, 1, readNow, g_fwad)) {
                    if (g_bDumpMode) std::cerr << "\nwad_unpack error: could not read in decomp callback!\n";
                    return 0LL;
                }
            }
        }
        return pDest + 0x80000;
    }
    std::map<std::string, WAD_FILE_HEADER*> m_list;
    void WAD_OffsetsToPointers(WAD_HEADER* wh) {
        uint8_t* bwh = (uint8_t*)wh;
        for (int assetIdx = 0; assetIdx < 17; assetIdx++) {
            if (wh->m_assets[assetIdx]) {
                auto pfh = (WAD_FILE_HEADER*)(bwh + (uint64_t)wh->m_assets[assetIdx]);
                wh->m_assets[assetIdx] = pfh;
                if (pfh->m_crypted)
                    EncryptDecryptWadString(&pfh->m_firstChar, pfh->m_fileLength);
                pfh->dump(g_bDumpMode, &m_list);
                /*if (pfh->f88) {
                    auto pfh88 = (WAD_FILE_HEADER *)(bwh + (uint64_t)pfh->f88);
                    pfh->f88 = (uint8_t *)pfh88;
                }*/
                while (pfh->m_nextFileSameAsset) {
                    auto pnfh = (WAD_FILE_HEADER*)(bwh + (uint64_t)pfh->m_nextFileSameAsset);
                    pfh->m_nextFileSameAsset = pnfh;
                    /*if (pnfh->f88) {
                        auto pnfh88 = (WAD_FILE_HEADER *)(bwh + (uint64_t)pnfh->f88);
                        pnfh->f88 = (uint8_t *)pnfh88;
                    }*/
                    if (pnfh->m_crypted)
                        EncryptDecryptWadString(&pnfh->m_firstChar, pnfh->m_fileLength);
                    pnfh->dump(g_bDumpMode, &m_list);
                    pfh = pnfh;
                }
            }
        }
        auto ptrAfterHeader = (int64_t*)(bwh + sizeof(WAD_HEADER));
        for (int64_t dirIdx = 0; dirIdx != 1024; dirIdx++) {
            auto dirOffset = ptrAfterHeader[dirIdx];
            if (dirOffset) {
                auto dirPtr = (WAD_FILE_HEADER*)(bwh + dirOffset);
                dirPtr->dump(g_bDumpMode, &m_list);
                ptrAfterHeader[dirIdx] = (int64_t)dirPtr;
                if (dirPtr) {
                    while (dirPtr->m_nextFile) {
                        auto filePtr = (WAD_FILE_HEADER*)(bwh + (int64_t)dirPtr->m_nextFile);
                        filePtr->dump(g_bDumpMode, &m_list);
                        dirPtr->m_nextFile = filePtr;
                        dirPtr = filePtr;
                    }
                }
            }
        }
    }
    int TJZIP_ParseDictionaryCode(uint8_t** pSrcPtr, uint8_t** pDestPtr, uint32_t* signature) {
        uint8_t* v3;
        uint8_t* v4;
        uint32_t v5;
        uint8_t* v9;
        int v10;
        int v11;
        uint32_t v12;
        int v13;
        int result;
        int32_t v15;
        uint8_t* v16;
        int v17;
        uint8_t* v18;
        int v19;
        uint8_t* v20;
        int v21;
        uint8_t* v22;
        uint8_t* v23;
        int v24;
        uint8_t* v25;
        uint8_t v26;
        uint8_t* v27;
        int v28;
        int v29;
        int v30;
        uint8_t* v31;
        uint32_t v32;

        v3 = *pDestPtr;
        v4 = *pSrcPtr + 1;
        v5 = **pSrcPtr;
        *pSrcPtr = v4;
        if (g_pCallbackAt && g_pCallbackAt - 32 <= v4) {
            g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
            v4 = *pSrcPtr;
        }
        v11 = *v4;
        v9 = v4 + 1;
        v10 = v11;
        *pSrcPtr = v9;
        if (g_pCallbackAt && g_pCallbackAt - 32 <= v9)
            g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
        v12 = v5 & 0xE0;
        if (v12 <= 0xBF) {
            v13 = (v5 >> 5) + 4;
            result = v5 & 3;
            v15 = v10 & 0xFFFFFCFF | (((v5 >> 2) & 3) << 8);
            goto LABEL_33;
        }
        if (v12 != 224) {
            if (v12 != 192)
                return 0;
            v16 = *pSrcPtr + 1;
            v17 = **pSrcPtr;
            *pSrcPtr = v16;
            if (g_pCallbackAt && g_pCallbackAt - 32 <= v16)
                g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
            v13 = (v5 & 0x1F) + 4;
            v15 = v17 & 0xFFFFC0FF | ((uint8_t)v10 >> 2 << 8);
            goto LABEL_32;
        }
        v18 = *pSrcPtr + 1;
        v19 = **pSrcPtr;
        *pSrcPtr = v18;
        if (g_pCallbackAt && g_pCallbackAt - 32 <= v18)
            g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
        if ((v5 & 0xF) != 0) {
            v13 = (v5 & 0xF) + 3;
        LABEL_31:
            v15 = (v5 << 10) & 0x4000 | ((uint8_t)v10 >> 2 << 8) | v19;
        LABEL_32:
            result = v10 & 3;
            goto LABEL_33;
        }
        v20 = *pSrcPtr + 1;
        v21 = **pSrcPtr;
        *pSrcPtr = v20;
        if (g_pCallbackAt && g_pCallbackAt - 32 <= v20)
            g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
        if (v10) {
            v13 = v10 + 18;
            v10 = (v10 & 0xFFFFFF00) | v19;
            v19 = v21;
            goto LABEL_31;
        }
        v25 = *pSrcPtr + 1;
        v26 = **pSrcPtr;
        *pSrcPtr = v25;
        if (g_pCallbackAt && g_pCallbackAt - 32 <= v25) {
            g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
            v25 = *pSrcPtr;
        }
        v29 = *v25;
        v27 = v25 + 1;
        v28 = v29;
        *pSrcPtr = v27;
        if (g_pCallbackAt && g_pCallbackAt - 32 <= v27) {
            v30 = v28;
            v31 = WAD_DecompCallback(g_pCallbackAt);
            v28 = v30;
            g_pCallbackAt = v31;
        }
        v32 = v21 & 0xFFFF00FF | ((uint8_t)v19 << 8);
        result = v26 & 3;
        if (v32) {
            v15 = (v5 << 10) & 0x4000 | (v26 >> 2 << 8) | v28;
            v13 = v32;
        LABEL_33:
            v22 = *pDestPtr;
            v23 = &v3[-v15];
            do {
                --v13;
                *v22 = *v23;
                v24 = *v23++;
                *signature = g_signatureTable[(uint8_t)*signature ^ v24] ^ (*signature >> 8);
                v22 = *pDestPtr + 1;
                *pDestPtr = v22;
            } while (v13);
        }
        return result;
    }
    void TJZIP_ParseRawDataBlock(uint8_t** pSrcPtr, uint8_t** pDestPtr, uint32_t* signature) {
        uint8_t* srcPtr;
        int chr;
        int v8;
        uint8_t* nextSrcPtr;
        int nextChr;
        uint8_t* v11;
        int v12;
        int v13;
        int v15;
        uint8_t v16;
        int v17;
        int v18;
        uint8_t v19;
        int v20;
        uint8_t* v21;
        uint8_t* v22;

        srcPtr = *pSrcPtr;
        chr = **pSrcPtr;
        if (!chr) {
            nextSrcPtr = srcPtr + 1;
            *pSrcPtr = srcPtr + 1;
            if (g_pCallbackAt && g_pCallbackAt - 32 <= nextSrcPtr) {
                g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
                nextSrcPtr = *pSrcPtr;
            }
            v11 = nextSrcPtr + 2;
            nextChr = *nextSrcPtr;
            *pSrcPtr = nextSrcPtr + 1;
            v12 = nextSrcPtr[1];
            *pSrcPtr = nextSrcPtr + 2;
            if (v12) {
                v13 = v12 << 8;
                v8 = v13 | nextChr;
            LABEL_12:
                if (g_pCallbackAt && g_pCallbackAt && g_pCallbackAt - 32 <= v11) {
                    g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
                    if (!v8)
                        return;
                    goto LABEL_21;
                }
            }
            else {
                v15 = nextSrcPtr[2];
                *pSrcPtr = nextSrcPtr + 3;
                if (v15) {
                    v16 = nextSrcPtr[3];
                    v11 = nextSrcPtr + 4;
                    *pSrcPtr = nextSrcPtr + 4;
                    v17 = (v15 << 16) | (v16 << 8);
                    v8 = v17 | nextChr;
                    goto LABEL_12;
                }
                else {
                    v18 = nextSrcPtr[3];
                    *pSrcPtr = nextSrcPtr + 4;
                    v19 = nextSrcPtr[4];
                    *pSrcPtr = nextSrcPtr + 5;
                    v11 = nextSrcPtr + 6;
                    v20 = (v18 << 24) | (uint16_t)(v19 << 8) | (nextSrcPtr[5] << 16);
                    *pSrcPtr = v11;
                    v8 = v20 | nextChr;
                    goto LABEL_12;
                }
            }
            if (!v8)
                return;
            goto LABEL_21;
        }
        *pSrcPtr = srcPtr + 1;
        v8 = chr + 2;
        if (g_pCallbackAt && g_pCallbackAt - 32 <= srcPtr + 1)
            g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
    LABEL_21:
        v21 = *pDestPtr;
        do {
            *v21 = **pSrcPtr;
            v22 = *pSrcPtr + 1;
            *signature = g_signatureTable[(uint8_t)*signature ^ **pSrcPtr] ^ (*signature >> 8);
            *pSrcPtr = v22;
            if (g_pCallbackAt && g_pCallbackAt - 32 <= v22)
                g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
            --v8;
            v21 = *pDestPtr + 1;
            *pDestPtr = v21;
        } while (v8);
    }
    uint32_t TJZIP_Decompress(uint8_t* pDecompressPtr, uint8_t* m_decomp_buf, uint32_t compressed_size, uint32_t* signature,
        uint8_t* pCallbackAt) {
        int dCode;
        uint8_t* srcPtr_;
        int cnt;
        uint8_t* destPtr_;
        int chr;
        uint8_t* destPtr;
        uint8_t* srcPtr;

        destPtr = m_decomp_buf;
        srcPtr = pDecompressPtr;
        *signature = 0;
        g_pCallbackAt = pCallbackAt;
        TJZIP_ParseRawDataBlock(&srcPtr, &destPtr, signature);
        while (srcPtr - pDecompressPtr < (int)compressed_size) {
            dCode = TJZIP_ParseDictionaryCode(&srcPtr, &destPtr, signature);
            if (dCode != 3) {
                srcPtr_ = srcPtr;
                if (srcPtr - pDecompressPtr < (int)compressed_size) {
                    cnt = dCode;
                    if (dCode) {
                        destPtr_ = destPtr;
                        do {
                            *destPtr_ = *srcPtr_;
                            chr = *srcPtr_++;
                            *signature = g_signatureTable[(uint8_t)*signature ^ chr] ^ (*signature >> 8);
                            if (g_pCallbackAt - 32 <= srcPtr_)
                                g_pCallbackAt = WAD_DecompCallback(g_pCallbackAt);
                            --cnt;
                            ++destPtr_;
                        } while (cnt);
                        destPtr = destPtr_;
                        srcPtr = srcPtr_;
                    }
                    else {
                        TJZIP_ParseRawDataBlock(&srcPtr, &destPtr, signature);
                    }
                }
            }
            if (pDecompressPtr < m_decomp_buf != srcPtr < destPtr)
                return 0LL;
        }
        *signature = ~*signature;
        return uint32_t(destPtr - m_decomp_buf);
    }

    std::map<std::string, WAD_FILE_HEADER*>::const_iterator m_curPosition;
    bool ReadHeader(tHeaderData* HeaderData) {
        if (m_curPosition == m_list.cend()) {
            m_curPosition = m_list.cbegin();
            return false;
        }
        strcpy_s(HeaderData->FileName, m_curPosition->first.c_str());
        HeaderData->UnpSize = HeaderData->PackSize = m_curPosition->second->m_fileLength;
        HeaderData->FileAttr = (m_curPosition->second->m_crypted) ? 0x2 : 0;
        return true;
    }
};

int main(int argc, char** argv)
{
    if (argc != 2) {
        std::cout << "wad_unpack v100966+ usage:\nwad_unpack.exe file.wad\n";
        return -1;
    }
    return WadUnpacker(argv[1]);
}
extern "C" {
    __declspec(dllexport) HANDLE __stdcall OpenArchive(tOpenArchiveData* ArchiveData) {
        auto ret = new WadUnpacker(ArchiveData->ArcName, false);
        if (ret->g_ret != 0) {
            delete ret;
            return 0;
        }
        return ret;
    }
    __declspec(dllexport) int __stdcall ReadHeader(HANDLE hArcData, tHeaderData* HeaderData) {
        auto obj = (WadUnpacker*)hArcData;
        return obj->ReadHeader(HeaderData) ? 0 : E_END_ARCHIVE;
    }
    __declspec(dllexport) int __stdcall ProcessFile(HANDLE hArcData, int Operation, char* DestPath, char* DestName) {
        auto obj = (WadUnpacker*)hArcData;
        if (obj->m_curPosition == obj->m_list.cend()) return E_NO_FILES;
        if (Operation == PK_EXTRACT) {
            char fullPath[260] = {};
            if (DestPath)
                strcpy_s(fullPath, DestPath);
            size_t len = strnlen_s(fullPath, 259);
            if (DestName) {
                if (len > 1 && fullPath[len - 1] != '\\')
                    fullPath[len - 1] = '\\';
                strcat_s(fullPath, DestName);
            }
            FILE* f = nullptr;
            fopen_s(&f, fullPath, "wb");
            if (f == nullptr) {
                obj->m_curPosition++;
                return E_ECREATE;
            }
            auto pf = obj->m_curPosition->second;
            if (pf->m_fileLength != fwrite(&pf->m_firstChar, 1, pf->m_fileLength, f)) {
                fclose(f);
                obj->m_curPosition++;
                return E_EWRITE;
            }
            fclose(f);
        }
        obj->m_curPosition++;
        return 0;
    }
    __declspec(dllexport) int __stdcall CloseArchive(HANDLE hArcData) {
        auto obj = (WadUnpacker*)hArcData;
        if (obj) delete obj;
        return 0;
    }
    __declspec(dllexport) void __stdcall SetChangeVolProc(HANDLE hArcData, tChangeVolProc pChangeVolProc1) {}
    __declspec(dllexport) void __stdcall SetProcessDataProc(HANDLE hArcData, tProcessDataProc pProcessDataProc) {
        auto obj = (WadUnpacker*)hArcData;
        obj->m_wcxProcess = pProcessDataProc;
    }
    __declspec(dllexport) int __stdcall GetPackerCaps() { return PK_CAPS_BY_CONTENT | PK_CAPS_SEARCHTEXT; }
    __declspec(dllexport) BOOL __stdcall CanYouHandleThisFile(char* FileName) {
        FILE* f = nullptr;
        fopen_s(&f, FileName, "rb");
        if (f) {
            char buf[4] = {};
            fread_s(buf, sizeof(buf), 1, sizeof(buf), f);
            fclose(f);
            return buf[0] == 'Z' && buf[1] == 'W' && buf[2] == 'F' && buf[3] == '!';
        }
        return 0;
    }
}
BOOL WINAPI DllMain(
    HINSTANCE hinstDLL,  // handle to DLL module
    DWORD fdwReason,     // reason for calling function
    LPVOID lpReserved)  // reserved
{
    // Perform actions based on the reason for calling.
    switch (fdwReason)     {
    case DLL_PROCESS_ATTACH:
        // Initialize once for each new process.
        // Return FALSE to fail DLL load.
        break;

    case DLL_THREAD_ATTACH:
        // Do thread-specific initialization.
        break;

    case DLL_THREAD_DETACH:
        // Do thread-specific cleanup.
        break;

    case DLL_PROCESS_DETACH:
        // Perform any necessary cleanup.
        break;
    }
    return TRUE;  // Successful DLL_PROCESS_ATTACH.
}