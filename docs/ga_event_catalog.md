# Event Catalog

This catalog summarizes earthquake events collected through the current data-source adapter. The same table format can be regenerated for other regions when event catalogs, station metadata, and high-rate GNSS data access are available.

中文：本文件汇总当前数据源适配器抓取到的地震事件。只要其他地区具备地震事件目录、台站元数据和高频 GNSS 数据接入，也可以用同样格式生成对应目录。

- Source database: `data/ga_availability/ga_1hz.sqlite`
- Event table: `ga_m6plus_events_au` (726 events)
- Station counts: distinct stations from `event_ga_station_candidates` within each radius
- Availability columns: from `event_ga_highrate_availability`
- Generated: 2026-05-20 11:53 UTC

## Build metadata

  - `min_magnitude`: `6.0`
  - `region_filter`: `USGS_bbox_-55.0_5.0_90.0_180.0`

## Columns

- `M`: event magnitude.
- `Lat` / `Lon`: event coordinates in decimal degrees.
- `Depth km`: USGS event depth.
- `Stations ≤200 km` and `Stations ≤300 km`: candidate GNSS stations around the event for the current data source.
- `Available`: stations with detected high-rate files for the event window.
- `Files`: matching high-rate files detected for the event.

## Events

| Event ID | Date UTC | M | Type | Lat | Lon | Depth km | Stations ≤200 km | Stations ≤300 km | Available | Complete | Partial | Files | Place |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| us6000sxqf | 2026-05-14T17:53:14.710Z | 6.2 | mww | -6.1980 | 130.3702 | 146.1 | 0 | 0 | 0 | 0 | 0 | 0 | 271 km WSW of Tual, Indonesia |
| us6000smj4 | 2026-04-04T10:34:28.266Z | 6.0 | mww | 4.8733 | 126.1392 | 67.0 | 0 | 1 | 0 | 0 | 0 | 0 | 95 km SE of Sarangani, Philippines |
| us6000slwy | 2026-04-02T03:23:52.561Z | 6.3 | mww | 1.1667 | 126.4787 | 28.0 | 0 | 0 | 0 | 0 | 0 | 0 | 109 km WNW of Ternate, Indonesia |
| us6000slss | 2026-04-01T22:48:13.063Z | 7.4 | mww | 1.0931 | 126.2354 | 35.0 | 0 | 0 | 0 | 0 | 0 | 0 | 129 km ESE of Bitung, Indonesia |
| us7000s8q0 | 2026-03-30T08:44:13.780Z | 7.3 | mww | -15.2865 | 167.5825 | 120.6 | 0 | 5 | 1 | 1 | 0 | 2 | 51 km ENE of Luganville, Vanuatu |
| us6000shnl | 2026-03-20T02:30:34.150Z | 6.1 | mww | -19.2794 | 168.3806 | 21.0 | 0 | 5 | 1 | 1 | 0 | 2 | 98 km WNW of Isangel, Vanuatu |
| us7000s2i2 | 2026-03-06T14:27:48.050Z | 6.2 | mww | -11.4700 | 163.0974 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 170 km SE of Kirakira, Solomon Islands |
| us7000s1ln | 2026-03-03T04:56:45.857Z | 6.2 | mww | 2.0076 | 96.6950 | 18.0 | 0 | 0 | 0 | 0 | 0 | 0 | 62 km SE of Sinabang, Indonesia |
| us6000sarf | 2026-02-22T07:43:25.409Z | 6.0 | mww | -21.7912 | 179.6322 | 636.3 | 0 | 1 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us6000s94q | 2026-02-14T02:27:42.554Z | 6.4 | mww | -14.9918 | 166.6216 | 43.0 | 0 | 0 | 0 | 0 | 0 | 0 | 48 km W of Port-Olry, Vanuatu |
| us7000rqjy | 2026-01-19T13:02:19.436Z | 6.0 | mww | -22.4395 | 170.3939 | 11.0 | 0 | 0 | 0 | 0 | 0 | 0 | 277 km ESE of Tadine, New Caledonia |
| us7000rnwd | 2026-01-10T14:58:23.726Z | 6.4 | mww | 3.7767 | 126.9922 | 31.0 | 0 | 0 | 0 | 0 | 0 | 0 | 247 km SE of Sarangani, Philippines |
| us7000rltg | 2026-01-01T01:53:01.809Z | 6.0 | mww | -45.6117 | 96.3592 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast Indian Ridge |
| us6000rwgh | 2025-12-22T10:31:27.918Z | 6.5 | mww | -5.7036 | 145.5368 | 107.0 | 0 | 3 | 0 | 0 | 0 | 0 | 45 km NNE of Goroka, Papua New Guinea |
| us7000re2g | 2025-11-27T04:56:24.368Z | 6.4 | mww | 2.7191 | 95.9543 | 17.0 | 0 | 0 | 0 | 0 | 0 | 0 | 54 km WNW of Sinabang, Indonesia |
| us6000rjx3 | 2025-10-28T14:40:18.481Z | 6.4 | mww | -6.7001 | 129.9887 | 142.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us6000rjkv | 2025-10-26T17:04:25.617Z | 6.2 | mww | -8.8524 | 123.9887 | 75.0 | 0 | 1 | 0 | 0 | 0 | 0 | 57 km NW of Pante Makasar, Timor Leste |
| us6000rjhm | 2025-10-25T23:28:02.544Z | 6.0 | mww | -12.3757 | 166.4018 | 34.0 | 0 | 0 | 0 | 0 | 0 | 0 | 194 km SSE of Lata, Solomon Islands |
| us6000rhg5 | 2025-10-16T05:48:52.788Z | 6.4 | mww | -2.1680 | 138.9531 | 18.0 | 0 | 0 | 0 | 0 | 0 | 0 | 192 km WNW of Abepura, Indonesia |
| us6000rfye | 2025-10-10T02:08:10.652Z | 6.3 | mww | -3.0764 | 147.9714 | 10.0 | 0 | 1 | 1 | 1 | 0 | 2 | 139 km SE of Lorengau, Papua New Guinea |
| us6000rfb2 | 2025-10-07T11:05:17.136Z | 6.6 | mww | -6.7359 | 146.8404 | 98.0 | 0 | 2 | 0 | 0 | 0 | 0 | 17 km W of Lae, Papua New Guinea |
| us6000rdta | 2025-09-30T16:49:43.533Z | 6.0 | mww | -7.2032 | 114.1844 | 19.5 | 0 | 2 | 0 | 0 | 0 | 0 | 31 km ESE of Kalianget, Indonesia |
| us7000qx1z | 2025-09-18T18:19:49.220Z | 6.0 | mww | -3.5961 | 135.4658 | 28.0 | 0 | 0 | 0 | 0 | 0 | 0 | 26 km S of Nabire, Indonesia |
| us7000qwir | 2025-09-16T16:59:46.550Z | 6.0 | mww | -5.5179 | 153.7354 | 31.0 | 0 | 1 | 0 | 0 | 0 | 0 | 208 km SE of Kokopo, Papua New Guinea |
| us7000quvp | 2025-09-08T21:47:48.117Z | 6.4 | mww | -21.0025 | 173.7046 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | Vanuatu region |
| us6000r0sa | 2025-08-14T16:22:34.235Z | 6.3 | mww | -11.6933 | 166.2048 | 45.0 | 0 | 0 | 0 | 0 | 0 | 0 | 115 km SSE of Lata, Solomon Islands |
| us6000r01m | 2025-08-12T08:24:23.409Z | 6.3 | mww | -2.0302 | 138.9660 | 14.0 | 0 | 0 | 0 | 0 | 0 | 0 | 195 km WNW of Abepura, Indonesia |
| us6000qw1a | 2025-07-29T17:53:40.918Z | 6.6 | mww | -23.4497 | 178.8580 | 553.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us6000qugg | 2025-07-23T20:50:43.792Z | 6.3 | mww | 0.4411 | 122.0874 | 142.0 | 0 | 0 | 0 | 0 | 0 | 0 | 109 km W of Gorontalo, Indonesia |
| us7000qcik | 2025-07-14T05:49:58.119Z | 6.7 | mww | -6.2201 | 131.2331 | 70.7 | 0 | 0 | 0 | 0 | 0 | 0 | 180 km WSW of Tual, Indonesia |
| us7000qb4s | 2025-07-07T12:53:44.013Z | 6.2 | mww | -47.1735 | 165.4962 | 22.0 | 0 | 8 | 0 | 0 | 0 | 0 | 213 km WSW of Riverton, New Zealand |
| us6000qisj | 2025-06-07T23:20:45.671Z | 6.2 | mww | -47.8272 | 115.9955 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | western Indian-Antarctic Ridge |
| us7000q0bm | 2025-05-20T15:05:59.387Z | 6.5 | mww | -3.7575 | 144.8116 | 16.8 | 0 | 1 | 0 | 0 | 0 | 0 | 89 km ENE of Angoram, Papua New Guinea |
| us7000pvtr | 2025-04-29T14:53:37.897Z | 6.8 | mww | -54.2616 | 155.6446 | 19.0 | 0 | 1 | 1 | 1 | 0 | 2 | Macquarie Island region |
| us7000pvt7 | 2025-04-29T13:16:32.562Z | 6.2 | mww | -48.1824 | 165.3571 | 10.6 | 0 | 6 | 0 | 0 | 0 | 0 | 285 km SW of Bluff, New Zealand |
| us7000pu62 | 2025-04-22T10:17:11.888Z | 6.2 | mww | 4.5538 | 127.8310 | 104.0 | 0 | 0 | 0 | 0 | 0 | 0 | 271 km SE of Pondaguitan, Philippines |
| us6000q6cs | 2025-04-16T01:42:59.524Z | 6.6 | mww | -47.8089 | 99.6130 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast Indian Ridge |
| us6000q5ka | 2025-04-12T03:47:08.682Z | 6.1 | mww | -4.7074 | 153.1423 | 52.0 | 0 | 1 | 0 | 0 | 0 | 0 | 104 km ESE of Kokopo, Papua New Guinea |
| us6000q41n | 2025-04-04T20:04:38.129Z | 6.9 | mww | -6.3025 | 151.6257 | 9.0 | 0 | 1 | 0 | 0 | 0 | 0 | 184 km ESE of Kimbe, Papua New Guinea |
| us7000pmem | 2025-03-25T01:43:11.796Z | 6.7 | mww | -46.7305 | 165.8632 | 21.0 | 0 | 8 | 0 | 0 | 0 | 0 | 170 km WSW of Riverton, New Zealand |
| us6000pvgx | 2025-02-25T22:55:45.917Z | 6.1 | mww | 0.3994 | 124.8407 | 21.7 | 0 | 0 | 0 | 0 | 0 | 0 | 45 km E of Modisi, Indonesia |
| us7000pfmk | 2025-02-23T18:16:18.073Z | 6.0 | mww | -11.3195 | 166.2902 | 36.0 | 0 | 0 | 0 | 0 | 0 | 0 | 85 km SE of Lata, Solomon Islands |
| us7000p0lv | 2024-12-21T15:30:53.399Z | 6.1 | mww | -17.7041 | 168.0033 | 47.0 | 0 | 5 | 0 | 0 | 0 | 0 | 33 km W of Port-Vila, Vanuatu |
| us7000nzf3 | 2024-12-17T01:47:25.741Z | 7.3 | mww | -17.6914 | 168.0842 | 54.4 | 0 | 5 | 1 | 1 | 0 | 2 | 24 km WNW of Port-Vila, Vanuatu |
| us7000nrwz | 2024-11-15T05:28:30.650Z | 6.6 | mww | -4.7548 | 153.2923 | 56.0 | 0 | 1 | 0 | 0 | 0 | 0 | 122 km ESE of Kokopo, Papua New Guinea |
| us7000nnz9 | 2024-10-30T12:18:51.671Z | 6.0 | mww | -4.4064 | 150.0827 | 509.0 | 0 | 1 | 0 | 0 | 0 | 0 | 126 km N of Kimbe, Papua New Guinea |
| us7000nhex | 2024-10-01T09:28:05.313Z | 6.1 | mww | -5.9828 | 124.8988 | 576.0 | 0 | 0 | 0 | 0 | 0 | 0 | 260 km ESE of Baubau, Indonesia |
| us6000ntxc | 2024-09-23T19:51:02.568Z | 6.0 | mww | -0.0469 | 122.8918 | 143.0 | 0 | 0 | 0 | 0 | 0 | 0 | 67 km SSW of Gorontalo, Indonesia |
| us7000nd4f | 2024-09-11T16:46:05.054Z | 6.3 | mww | -3.2871 | 146.4088 | 8.0 | 0 | 1 | 0 | 0 | 0 | 0 | 168 km SW of Lorengau, Papua New Guinea |
| us6000nps8 | 2024-09-05T01:03:15.672Z | 6.2 | mww | -3.5428 | 144.1953 | 7.0 | 0 | 1 | 0 | 0 | 0 | 0 | 59 km NNE of Angoram, Papua New Guinea |
| us6000np3z | 2024-09-01T20:13:34.201Z | 6.4 | mww | -6.8295 | 155.5297 | 39.0 | 0 | 0 | 0 | 0 | 0 | 0 | 56 km S of Panguna, Papua New Guinea |
| us7000n0s8 | 2024-07-22T05:04:27.743Z | 6.1 | mww | -15.5073 | 168.1241 | 4.0 | 0 | 5 | 1 | 1 | 0 | 2 | 99 km NE of Norsup, Vanuatu |
| us7000mu8s | 2024-06-24T08:03:37.383Z | 6.3 | mww | -14.6255 | 167.2426 | 149.0 | 0 | 0 | 0 | 0 | 0 | 0 | 49 km NNE of Port-Olry, Vanuatu |
| us6000n102 | 2024-05-25T22:23:15.997Z | 6.3 | mww | -17.1173 | 167.8706 | 22.0 | 0 | 5 | 1 | 1 | 0 | 2 | 83 km NW of Port-Vila, Vanuatu |
| us6000mx5c | 2024-05-08T08:17:15.894Z | 6.1 | mww | -15.1324 | 168.0214 | 19.2 | 0 | 5 | 1 | 1 | 0 | 2 | 101 km ENE of Luganville, Vanuatu |
| us6000mwjd | 2024-05-05T18:33:11.021Z | 6.1 | mww | -3.3167 | 130.9618 | 16.0 | 0 | 0 | 0 | 0 | 0 | 0 | 154 km WSW of Fakfak, Indonesia |
| us6000muc0 | 2024-04-27T16:29:50.643Z | 6.1 | mww | -8.0050 | 107.2798 | 59.7 | 0 | 2 | 0 | 0 | 0 | 0 | 91 km S of Banjar, Indonesia |
| us7000mc2t | 2024-04-14T20:56:28.201Z | 6.5 | mww | -5.8565 | 151.0953 | 49.0 | 0 | 1 | 0 | 0 | 0 | 0 | 111 km ESE of Kimbe, Papua New Guinea |
| us7000maxr | 2024-04-09T09:47:59.810Z | 6.4 | mww | 2.6982 | 127.0624 | 22.0 | 0 | 0 | 0 | 0 | 0 | 0 | 150 km NW of Tobelo, Indonesia |
| us7000m86i | 2024-03-27T01:28:17.689Z | 6.4 | mww | -21.0715 | 173.7373 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | Vanuatu region |
| us6000mksx | 2024-03-23T20:22:04.348Z | 6.9 | mww | -4.1292 | 143.1340 | 41.5 | 0 | 2 | 0 | 0 | 0 | 0 | 36 km ENE of Ambunti, Papua New Guinea |
| us6000mkfz | 2024-03-22T08:52:58.999Z | 6.4 | mww | -5.8754 | 112.3646 | 9.5 | 0 | 1 | 0 | 0 | 0 | 0 | 110 km N of Paciran, Indonesia |
| us6000milg | 2024-03-13T15:13:22.779Z | 6.0 | mww | -5.8310 | 150.6843 | 44.0 | 0 | 1 | 0 | 0 | 0 | 0 | 68 km ESE of Kimbe, Papua New Guinea |
| us7000lt73 | 2024-01-23T14:33:45.022Z | 6.3 | mww | -17.9827 | 168.0499 | 31.0 | 0 | 5 | 1 | 1 | 0 | 2 | 39 km SW of Port-Vila, Vanuatu |
| us6000m2jp | 2024-01-08T20:48:42.361Z | 6.7 | mww | 4.9225 | 126.1575 | 62.6 | 0 | 1 | 0 | 0 | 0 | 0 | 93 km SE of Sarangani, Philippines |
| us6000m0n6 | 2023-12-30T17:16:23.833Z | 6.3 | mww | -2.9934 | 139.3720 | 33.0 | 0 | 0 | 0 | 0 | 0 | 0 | 146 km WSW of Abepura, Indonesia |
| us7000lgwp | 2023-12-07T12:56:30.184Z | 7.1 | mww | -20.6152 | 169.3089 | 48.0 | 0 | 0 | 0 | 0 | 0 | 0 | 118 km S of Isangel, Vanuatu |
| us7000le6w | 2023-11-27T21:46:42.183Z | 6.5 | mww | -3.5605 | 144.0313 | 10.0 | 0 | 2 | 0 | 0 | 0 | 0 | 44 km E of Wewak, Papua New Guinea |
| us6000lq00 | 2023-11-22T04:47:31.590Z | 6.7 | mww | -14.9603 | 167.9718 | 13.0 | 0 | 0 | 0 | 0 | 0 | 0 | 97 km E of Port-Olry, Vanuatu |
| us6000lpyx | 2023-11-22T02:48:51.641Z | 6.0 | mww | 1.7827 | 127.1887 | 102.0 | 0 | 0 | 0 | 0 | 0 | 0 | 91 km W of Tobelo, Indonesia |
| us7000lali | 2023-11-13T07:43:34.115Z | 6.1 | mww | -3.8855 | 151.0670 | 10.0 | 0 | 1 | 0 | 0 | 0 | 0 | 126 km WNW of Rabaul, Papua New Guinea |
| us7000la7r | 2023-11-10T20:45:11.772Z | 6.1 | mww | -6.0976 | 130.0606 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us7000l9ku | 2023-11-08T13:02:06.115Z | 6.7 | mww | -6.1310 | 129.8738 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us7000l9h4 | 2023-11-08T04:53:49.631Z | 7.1 | mww | -6.4160 | 129.5466 | 6.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us7000l9h2 | 2023-11-08T04:52:51.393Z | 6.7 | mwb | -6.4442 | 129.7518 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us7000l85t | 2023-11-01T21:04:48.023Z | 6.1 | mww | -10.0561 | 123.7541 | 51.0 | 0 | 1 | 0 | 0 | 0 | 0 | 20 km NE of Kupang, Indonesia |
| us7000l7b6 | 2023-10-29T04:32:07.316Z | 6.0 | mww | -19.3871 | 168.8034 | 68.0 | 0 | 5 | 1 | 1 | 0 | 2 | 53 km WNW of Isangel, Vanuatu |
| us6000lews | 2023-10-11T20:04:58.206Z | 6.3 | mww | -52.0446 | 139.6131 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | west of Macquarie Island |
| us6000ldqf | 2023-10-07T08:40:11.361Z | 6.9 | mww | -5.4749 | 146.1439 | 52.0 | 0 | 2 | 0 | 0 | 0 | 0 | 48 km SE of Madang, Papua New Guinea |
| us6000ldqd | 2023-10-07T08:34:26.985Z | 6.7 | mww | -5.5729 | 146.1380 | 55.0 | 0 | 2 | 0 | 0 | 0 | 0 | 54 km SE of Madang, Papua New Guinea |
| us6000lbdi | 2023-09-28T14:40:25.892Z | 6.1 | mww | -15.5866 | 167.7410 | 125.0 | 0 | 5 | 1 | 1 | 0 | 2 | 62 km E of Luganville, Vanuatu |
| us7000kx7j | 2023-09-21T21:11:48.933Z | 6.1 | mww | -14.0192 | 167.2467 | 185.0 | 0 | 0 | 0 | 0 | 0 | 0 | Vanuatu |
| us7000kv0k | 2023-09-11T12:51:33.104Z | 6.0 | mww | 1.1246 | 127.4888 | 151.0 | 0 | 0 | 0 | 0 | 0 | 0 | 38 km NNE of Ternate, Indonesia |
| us7000kulj | 2023-09-09T14:43:24.563Z | 6.0 | mww | 0.0018 | 119.7663 | 13.0 | 0 | 0 | 0 | 0 | 0 | 0 | 101 km N of Palu, Indonesia |
| us7000krjx | 2023-08-28T19:55:30.875Z | 7.1 | mww | -6.7888 | 116.5211 | 500.0 | 0 | 1 | 0 | 0 | 0 | 0 | 180 km NNE of Gili Air, Indonesia |
| us7000knq0 | 2023-08-16T12:47:39.720Z | 6.5 | mww | -13.8882 | 167.2249 | 188.0 | 0 | 0 | 0 | 0 | 0 | 0 | 35 km W of Sola, Vanuatu |
| us6000kvmq | 2023-07-26T12:44:35.646Z | 6.4 | mww | -14.7400 | 167.9135 | 13.0 | 0 | 0 | 0 | 0 | 0 | 0 | 96 km ENE of Port-Olry, Vanuatu |
| us7000khw8 | 2023-07-24T02:49:56.186Z | 6.0 | mww | -24.0956 | 178.7423 | 523.0 | 0 | 0 | 0 | 0 | 0 | 0 | 665 km S of Suva, Fiji |
| us7000k9jv | 2023-06-19T11:18:11.960Z | 6.2 | mww | -4.4729 | 144.8345 | 23.8 | 0 | 2 | 0 | 0 | 0 | 0 | 96 km ESE of Angoram, Papua New Guinea |
| us7000k54z | 2023-05-31T02:21:23.997Z | 6.3 | mww | -49.6093 | 163.8553 | 14.8 | 0 | 0 | 0 | 0 | 0 | 0 | Auckland Islands, New Zealand region |
| us7000k3h5 | 2023-05-24T15:49:34.402Z | 6.2 | mww | -6.9484 | 129.5293 | 158.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us7000k36n | 2023-05-23T06:41:58.609Z | 6.1 | mww | -22.9954 | 170.3067 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 290 km E of Vao, New Caledonia |
| us6000kdnw | 2023-05-21T15:45:13.303Z | 6.1 | mww | -10.2725 | 161.4437 | 82.3 | 0 | 1 | 1 | 1 | 0 | 2 | 55 km WNW of Kirakira, Solomon Islands |
| us6000kdcu | 2023-05-20T02:09:54.333Z | 6.5 | mww | -22.9560 | 170.5524 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000kdce | 2023-05-20T01:50:59.158Z | 7.1 | mww | -23.0421 | 170.5603 | 27.3 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000kd0n | 2023-05-19T02:57:03.172Z | 7.7 | mww | -23.2063 | 170.7423 | 18.1 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us7000jwhe | 2023-04-28T03:13:48.476Z | 6.6 | mww | -25.1498 | 178.4274 | 563.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us7000jwhc | 2023-04-28T03:13:44.419Z | 6.0 | mb | -25.1471 | 178.5065 | 587.6 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us7000jvl3 | 2023-04-24T20:00:57.265Z | 7.1 | mww | -0.8082 | 98.5112 | 34.0 | 0 | 1 | 0 | 0 | 0 | 0 | 171 km SSE of Teluk Dalam, Indonesia |
| us6000k6ai | 2023-04-22T08:23:42.033Z | 6.2 | mww | -5.2611 | 125.5850 | 4.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us6000k5gu | 2023-04-19T09:06:03.150Z | 6.3 | mww | -5.9496 | 149.6350 | 40.0 | 0 | 0 | 0 | 0 | 0 | 0 | 30 km NNE of Kandrian, Papua New Guinea |
| us6000k587 | 2023-04-18T04:31:42.284Z | 6.7 | mww | -22.3188 | 179.4509 | 580.0 | 0 | 1 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us6000k49j | 2023-04-14T09:55:45.220Z | 7.0 | mww | -6.0413 | 112.0478 | 597.0 | 0 | 2 | 0 | 0 | 0 | 0 | Java, Indonesia |
| us6000k1qa | 2023-04-03T14:59:41.845Z | 6.1 | mww | 0.8388 | 98.8350 | 84.0 | 0 | 1 | 0 | 0 | 0 | 0 | 77 km SW of Padangsidempuan, Indonesia |
| us6000k1id | 2023-04-02T18:04:11.261Z | 7.0 | mww | -4.3229 | 143.1658 | 70.0 | 0 | 2 | 0 | 0 | 0 | 0 | 40 km ESE of Ambunti, Papua New Guinea |
| us6000k05c | 2023-03-27T22:19:15.181Z | 6.2 | mww | -8.2322 | 158.9118 | 79.0 | 0 | 1 | 1 | 1 | 0 | 2 | Solomon Islands |
| us7000jjp7 | 2023-03-14T00:49:08.469Z | 6.3 | mww | -5.4205 | 146.8342 | 213.0 | 0 | 2 | 0 | 0 | 0 | 0 | 118 km E of Madang, Papua New Guinea |
| usd000j5jt | 2023-03-02T18:04:30.810Z | 6.5 | mww | -15.3766 | 166.3907 | 17.0 | 0 | 0 | 0 | 0 | 0 | 0 | 83 km WSW of Port-Olry, Vanuatu |
| us7000jgfd | 2023-03-01T05:36:14.834Z | 6.6 | mww | -4.8255 | 149.5041 | 600.9 | 0 | 0 | 0 | 0 | 0 | 0 | 106 km NW of Kimbe, Papua New Guinea |
| us6000jrlp | 2023-02-25T21:24:47.577Z | 6.2 | mww | -6.0883 | 149.8280 | 34.0 | 0 | 0 | 0 | 0 | 0 | 0 | 33 km ENE of Kandrian, Papua New Guinea |
| us6000jr32 | 2023-02-23T20:02:47.541Z | 6.3 | mww | 3.2796 | 128.1356 | 92.0 | 0 | 0 | 0 | 0 | 0 | 0 | 172 km N of Tobelo, Indonesia |
| us6000jpl7 | 2023-02-17T09:37:34.656Z | 6.1 | mww | -6.6176 | 132.1060 | 39.7 | 0 | 0 | 0 | 0 | 0 | 0 | 130 km SSW of Tual, Indonesia |
| us7000j553 | 2023-01-18T06:06:11.454Z | 7.0 | mwc | 2.7306 | 127.0221 | 29.7 | 0 | 0 | 0 | 0 | 0 | 0 | 156 km NW of Tobelo, Indonesia |
| us7000j511 | 2023-01-18T00:34:45.151Z | 6.0 | mww | -0.0116 | 123.1998 | 154.0 | 0 | 0 | 0 | 0 | 0 | 0 | 62 km SSE of Gorontalo, Indonesia |
| us7000j4kr | 2023-01-15T22:29:58.940Z | 6.1 | mww | 1.9837 | 97.9979 | 37.0 | 0 | 0 | 0 | 0 | 0 | 0 | 40 km SE of Singkil, Indonesia |
| us7000j36j | 2023-01-09T17:47:35.037Z | 7.6 | mww | -7.0586 | 130.0090 | 105.0 | 0 | 0 | 0 | 0 | 0 | 0 | Pulau Pulau Tanimbar, Indonesia |
| us7000j2yw | 2023-01-08T12:32:42.372Z | 7.0 | mww | -14.9467 | 166.8791 | 29.0 | 0 | 0 | 0 | 0 | 0 | 0 | 23 km WNW of Port-Olry, Vanuatu |
| us7000j0n4 | 2022-12-28T16:34:19.271Z | 6.1 | mww | -21.2566 | 171.3773 | 4.0 | 0 | 0 | 0 | 0 | 0 | 0 | 289 km SE of Isangel, Vanuatu |
| us7000irfm | 2022-11-22T02:37:57.529Z | 6.0 | mww | -9.8203 | 159.4589 | 10.0 | 0 | 1 | 0 | 0 | 0 | 0 | Solomon Islands |
| us7000irfb | 2022-11-22T02:03:06.891Z | 7.0 | mww | -9.8198 | 159.6033 | 14.0 | 0 | 1 | 1 | 1 | 0 | 1 | 18 km SW of Malango, Solomon Islands |
| us7000iqpn | 2022-11-18T13:37:08.687Z | 6.9 | mww | -4.9043 | 100.7862 | 25.0 | 0 | 0 | 0 | 0 | 0 | 0 | 204 km SW of Bengkulu, Indonesia |
| us7000ipkb | 2022-11-14T05:04:11.890Z | 6.1 | mww | -26.0027 | 178.2034 | 630.2 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us7000inht | 2022-11-09T10:14:33.810Z | 6.6 | mww | -25.5781 | 178.2612 | 624.5 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us7000ingi | 2022-11-09T09:51:04.068Z | 7.0 | mwb | -26.0901 | 178.3427 | 660.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us7000ingh | 2022-11-09T09:38:42.828Z | 6.8 | mww | -26.0077 | 178.2776 | 630.4 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us6000itgv | 2022-10-13T22:20:20.620Z | 6.4 | mww | -4.8120 | 153.5906 | 72.0 | 0 | 1 | 0 | 0 | 0 | 0 | 155 km ESE of Kokopo, Papua New Guinea |
| us7000iaka | 2022-09-23T20:52:58.398Z | 6.2 | mww | 3.8109 | 96.0514 | 42.2 | 0 | 0 | 0 | 0 | 0 | 0 | 37 km SSW of Meulaboh, Indonesia |
| us7000i7ya | 2022-09-14T11:04:06.558Z | 7.0 | mww | -21.1909 | 170.2666 | 137.0 | 0 | 0 | 0 | 0 | 0 | 0 | 209 km SSE of Isangel, Vanuatu |
| us6000iitd | 2022-09-10T23:47:00.233Z | 7.6 | mww | -6.2944 | 146.5038 | 116.0 | 0 | 2 | 0 | 0 | 0 | 0 | 70 km E of Kainantu, Papua New Guinea |
| us6000iisb | 2022-09-10T23:10:43.721Z | 6.0 | mww | -1.1490 | 98.6540 | 20.0 | 0 | 1 | 0 | 0 | 0 | 0 | 173 km WSW of Pariaman, Indonesia |
| us6000iikp | 2022-09-10T00:05:12.947Z | 6.2 | mww | -2.2313 | 138.1784 | 21.0 | 0 | 0 | 0 | 0 | 0 | 0 | 260 km ESE of Biak, Indonesia |
| us6000iika | 2022-09-09T23:31:47.409Z | 6.2 | mww | -2.2492 | 138.1979 | 18.0 | 0 | 0 | 0 | 0 | 0 | 0 | Papua, Indonesia |
| us7000i4st | 2022-09-02T22:39:51.520Z | 6.1 | mww | -5.6524 | 148.7121 | 125.0 | 0 | 2 | 0 | 0 | 0 | 0 | 110 km WNW of Kandrian, Papua New Guinea |
| us7000i38s | 2022-08-29T03:29:13.691Z | 6.2 | mww | -0.9880 | 98.6046 | 17.0 | 0 | 1 | 0 | 0 | 0 | 0 | 173 km WSW of Pariaman, Indonesia |
| us6000id0t | 2022-08-23T14:31:39.374Z | 6.2 | mww | -5.0926 | 103.0790 | 45.3 | 0 | 0 | 0 | 0 | 0 | 0 | 119 km S of Pagar Alam, Indonesia |
| us6000iav7 | 2022-08-14T21:04:44.737Z | 6.4 | mww | -22.0781 | 170.9660 | 78.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000i1ms | 2022-07-11T21:10:47.785Z | 6.0 | mww | -18.1404 | 168.9678 | 10.0 | 0 | 5 | 0 | 0 | 0 | 0 | 82 km ESE of Port-Vila, Vanuatu |
| us7000hcwg | 2022-05-27T02:36:05.556Z | 6.2 | mww | -8.2572 | 127.2079 | 49.0 | 0 | 0 | 0 | 0 | 0 | 0 | 37 km NE of Lospalos, Timor Leste |
| us7000hcqw | 2022-05-26T15:37:58.560Z | 6.6 | mww | -22.8282 | 172.1298 | 15.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000hn1e | 2022-05-22T07:06:28.470Z | 6.3 | mww | -26.2125 | 178.4501 | 603.8 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us6000hm9j | 2022-05-19T10:13:31.625Z | 6.9 | mww | -54.1320 | 159.0545 | 10.0 | 0 | 1 | 1 | 1 | 0 | 2 | Macquarie Island region |
| us7000h87i | 2022-05-09T22:33:06.873Z | 6.3 | mww | -3.3591 | 146.3506 | 10.0 | 0 | 1 | 0 | 0 | 0 | 0 | 178 km SW of Lorengau, Papua New Guinea |
| us7000h5mc | 2022-04-28T13:21:13.122Z | 6.1 | mww | -3.9148 | 146.6901 | 10.0 | 0 | 1 | 1 | 1 | 0 | 2 | 175 km NE of Madang, Papua New Guinea |
| us7000h2u9 | 2022-04-17T07:46:35.635Z | 6.1 | mww | -15.7044 | 167.8457 | 196.0 | 0 | 5 | 0 | 0 | 0 | 0 | Vanuatu |
| us7000h1lv | 2022-04-13T03:00:56.312Z | 6.1 | mww | -4.4297 | 152.0242 | 149.0 | 0 | 1 | 0 | 0 | 0 | 0 | 28 km WSW of Kokopo, Papua New Guinea |
| us7000h0yj | 2022-04-09T20:52:38.456Z | 6.3 | mww | -16.3146 | 166.8601 | 17.0 | 0 | 5 | 0 | 0 | 0 | 0 | 63 km WSW of Norsup, Vanuatu |
| usd000h551 | 2022-04-04T16:06:57.662Z | 6.0 | mww | -17.4723 | 167.8625 | 31.0 | 0 | 5 | 0 | 0 | 0 | 0 | 56 km WNW of Port-Vila, Vanuatu |
| us7000gysz | 2022-03-31T19:50:40.985Z | 6.4 | mww | -22.6577 | 170.8084 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us7000gymk | 2022-03-31T05:44:01.146Z | 7.0 | mww | -22.5860 | 170.3744 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us7000gyj0 | 2022-03-30T20:56:58.105Z | 6.9 | mww | -22.6660 | 170.3659 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 284 km ESE of Tadine, New Caledonia |
| us7000gwpw | 2022-03-23T21:57:00.144Z | 6.0 | mww | -15.0687 | 167.4522 | 115.0 | 0 | 0 | 0 | 0 | 0 | 0 | Vanuatu |
| us6000h48e | 2022-03-13T21:09:22.258Z | 6.7 | mww | -0.6294 | 98.6259 | 28.0 | 0 | 1 | 0 | 0 | 0 | 0 | 166 km W of Pariaman, Indonesia |
| us6000gzyg | 2022-02-25T01:39:26.554Z | 6.1 | mww | 0.2190 | 100.1006 | 4.0 | 0 | 1 | 0 | 0 | 0 | 0 | 65 km NNW of Bukittinggi, Indonesia |
| us7000glex | 2022-02-16T20:21:06.737Z | 6.8 | mww | -23.7682 | 179.9981 | 535.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us7000gi25 | 2022-02-04T20:25:09.549Z | 6.3 | mww | -48.0330 | 99.4949 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast Indian Ridge |
| us7000gh1g | 2022-02-01T19:25:10.031Z | 6.0 | mww | -7.4830 | 128.3132 | 119.0 | 0 | 0 | 0 | 0 | 0 | 0 | 184 km NE of Lospalos, Timor Leste |
| us7000ge38 | 2022-01-22T02:26:13.323Z | 6.0 | mww | 3.6724 | 126.6596 | 21.0 | 0 | 0 | 0 | 0 | 0 | 0 | 232 km SE of Sarangani, Philippines |
| us7000gcfv | 2022-01-16T12:52:08.025Z | 6.1 | mww | -6.4492 | 154.8224 | 379.0 | 0 | 0 | 0 | 0 | 0 | 0 | 74 km WSW of Panguna, Papua New Guinea |
| us7000gbu4 | 2022-01-14T09:05:41.461Z | 6.6 | mww | -6.8600 | 105.2887 | 33.0 | 0 | 2 | 0 | 0 | 0 | 0 | 80 km SW of Labuan, Indonesia |
| us7000gag3 | 2022-01-10T00:06:30.834Z | 6.2 | mww | -33.7823 | 179.5740 | 7.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Kermadec Islands |
| us7000g90c | 2022-01-04T20:55:46.858Z | 6.0 | mww | -4.8065 | 125.0808 | 544.0 | 0 | 0 | 0 | 0 | 0 | 0 | 284 km E of Katabu, Indonesia |
| us7000g8kq | 2022-01-03T02:09:44.647Z | 6.0 | mww | -13.1864 | 166.8148 | 104.0 | 0 | 0 | 0 | 0 | 0 | 0 | 110 km NW of Sola, Vanuatu |
| us7000g7lx | 2021-12-29T18:25:51.962Z | 7.3 | mww | -7.5482 | 127.5773 | 165.5 | 0 | 0 | 0 | 0 | 0 | 0 | 125 km NNE of Lospalos, Timor Leste |
| us6000gdma | 2021-12-19T16:28:22.616Z | 6.2 | mww | -16.3139 | 178.5777 | 10.0 | 0 | 11 | 0 | 0 | 0 | 0 | 85 km W of Labasa, Fiji |
| us6000gc2a | 2021-12-14T03:20:23.809Z | 7.3 | mww | -7.6033 | 122.2274 | 14.3 | 0 | 1 | 0 | 0 | 0 | 0 | Flores Sea |
| us6000g944 | 2021-12-04T23:47:55.581Z | 6.0 | mww | 4.0932 | 128.1359 | 149.0 | 0 | 0 | 0 | 0 | 0 | 0 | 261 km N of Tobelo, Indonesia |
| us6000g8te | 2021-11-30T10:37:35.539Z | 6.1 | mww | -3.6249 | 151.3524 | 10.0 | 0 | 1 | 0 | 0 | 0 | 0 | 110 km NW of Rabaul, Papua New Guinea |
| us6000g7v8 | 2021-11-30T10:36:18.077Z | 6.3 | mww | -3.5226 | 151.1847 | 10.0 | 0 | 1 | 0 | 0 | 0 | 0 | 113 km SSE of Kavieng, Papua New Guinea |
| us7000fwzz | 2021-11-25T12:04:05.721Z | 6.1 | mww | -10.7451 | 166.5074 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 77 km E of Lata, Solomon Islands |
| us7000fv37 | 2021-11-18T14:08:04.800Z | 6.2 | mww | -5.3122 | 153.7074 | 34.0 | 0 | 1 | 0 | 0 | 0 | 0 | 192 km SE of Kokopo, Papua New Guinea |
| us7000ft0f | 2021-11-10T17:46:40.379Z | 6.0 | mww | -4.3244 | 134.1805 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 181 km SW of Nabire, Indonesia |
| us7000fs08 | 2021-11-06T14:37:36.731Z | 6.0 | mww | -0.0451 | 124.2812 | 34.0 | 0 | 0 | 0 | 0 | 0 | 0 | 150 km ESE of Gorontalo, Indonesia |
| us7000fqjc | 2021-11-01T17:04:16.557Z | 6.0 | mww | 0.2081 | 96.7090 | 8.0 | 0 | 0 | 0 | 0 | 0 | 0 | 253 km S of Sinabang, Indonesia |
| us6000fwd5 | 2021-10-21T08:10:43.027Z | 6.1 | mww | -25.3160 | 179.6040 | 487.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us6000fvkf | 2021-10-18T07:26:51.639Z | 6.2 | mww | -13.6900 | 167.0396 | 93.0 | 0 | 0 | 0 | 0 | 0 | 0 | 59 km WNW of Sola, Vanuatu |
| us6000furk | 2021-10-15T02:44:59.320Z | 6.4 | mww | -8.8783 | 158.4642 | 33.0 | 0 | 1 | 1 | 1 | 0 | 2 | 148 km WSW of Buala, Solomon Islands |
| us6000ft9g | 2021-10-09T10:58:31.956Z | 6.9 | mww | -21.1889 | 174.5221 | 535.0 | 0 | 0 | 0 | 0 | 0 | 0 | Vanuatu region |
| us6000fr0b | 2021-10-02T06:29:17.897Z | 7.3 | mww | -21.1265 | 174.8958 | 527.0 | 0 | 0 | 0 | 0 | 0 | 0 | Vanuatu region |
| us6000f7vg | 2021-08-18T10:10:05.238Z | 6.9 | mww | -14.8818 | 167.0585 | 93.0 | 0 | 0 | 0 | 0 | 0 | 0 | 17 km N of Port-Olry, Vanuatu |
| us6000f1ea | 2021-08-02T05:01:19.974Z | 6.0 | mww | -4.4990 | 133.9580 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 182 km NE of Tual, Indonesia |
| us6000ez5x | 2021-07-26T12:09:06.655Z | 6.3 | mww | -0.7679 | 121.9083 | 11.0 | 0 | 0 | 0 | 0 | 0 | 0 | 99 km WNW of Luwuk, Indonesia |
| us6000exmx | 2021-07-21T14:26:00.341Z | 6.0 | mww | -3.2314 | 146.7999 | 8.4 | 0 | 1 | 1 | 1 | 0 | 2 | 142 km SSW of Lorengau, Papua New Guinea |
| us6000etxj | 2021-07-10T00:43:55.986Z | 6.1 | mww | 2.9494 | 126.4984 | 44.3 | 0 | 0 | 0 | 0 | 0 | 0 | 215 km NW of Tobelo, Indonesia |
| us7000e9bi | 2021-06-03T10:09:58.295Z | 6.2 | mww | 0.3165 | 126.2911 | 26.0 | 0 | 0 | 0 | 0 | 0 | 0 | 132 km WSW of Ternate, Indonesia |
| us7000e2zt | 2021-05-14T06:33:07.879Z | 6.7 | mww | 0.1364 | 96.6442 | 11.0 | 0 | 0 | 0 | 0 | 0 | 0 | 260 km S of Sinabang, Indonesia |
| us7000e13b | 2021-05-07T15:21:13.760Z | 6.1 | mww | -54.4135 | 144.2159 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | west of Macquarie Island |
| us7000dxsy | 2021-04-27T08:05:31.717Z | 6.1 | mww | -3.4070 | 145.5171 | 10.0 | 0 | 1 | 1 | 1 | 0 | 2 | 176 km ENE of Angoram, Papua New Guinea |
| us6000e30x | 2021-04-19T23:58:22.503Z | 6.1 | mww | 0.1831 | 96.5601 | 9.0 | 0 | 0 | 0 | 0 | 0 | 0 | 254 km S of Sinabang, Indonesia |
| us6000e0lk | 2021-04-10T11:38:31.524Z | 6.0 | mww | -3.4440 | 145.7329 | 9.0 | 0 | 1 | 1 | 1 | 0 | 2 | 196 km N of Madang, Papua New Guinea |
| us6000e0k5 | 2021-04-10T09:30:43.306Z | 6.1 | mww | 4.1322 | 124.6443 | 300.0 | 0 | 1 | 0 | 0 | 0 | 0 | 167 km SSW of Sarangani, Philippines |
| us6000e0iy | 2021-04-10T07:00:15.485Z | 6.0 | mww | -8.5707 | 112.5054 | 67.0 | 0 | 3 | 0 | 0 | 0 | 0 | 45 km S of Sumberpucung, Indonesia |
| us6000dz3c | 2021-04-05T07:37:52.938Z | 6.1 | mww | -37.4600 | 179.6324 | 24.0 | 0 | 39 | 0 | 0 | 0 | 0 | 194 km NE of Gisborne, New Zealand |
| us7000dg8x | 2021-03-06T00:16:22.227Z | 6.3 | mww | -37.5763 | 179.5947 | 13.0 | 0 | 42 | 0 | 0 | 0 | 0 | 183 km NE of Gisborne, New Zealand |
| us7000dfhs | 2021-03-04T16:53:11.135Z | 6.1 | mww | -14.4334 | 167.3326 | 173.3 | 0 | 0 | 0 | 0 | 0 | 0 | 66 km SSW of Sola, Vanuatu |
| us7000dffl | 2021-03-04T13:27:34.647Z | 7.3 | mww | -37.4787 | 179.4576 | 10.0 | 0 | 45 | 0 | 0 | 0 | 0 | 182 km NE of Gisborne, New Zealand |
| us6000dila | 2021-02-18T06:37:30.717Z | 6.2 | mww | -18.9515 | 168.0675 | 14.0 | 0 | 5 | 0 | 0 | 0 | 0 | 136 km S of Port-Vila, Vanuatu |
| us6000dii3 | 2021-02-17T22:49:38.110Z | 6.1 | mww | -23.1842 | 171.7786 | 12.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000dhxn | 2021-02-16T00:49:25.141Z | 6.2 | mww | -17.8292 | 167.5413 | 13.0 | 0 | 5 | 0 | 0 | 0 | 0 | 82 km W of Port-Vila, Vanuatu |
| us6000dgkr | 2021-02-11T06:52:28.131Z | 6.0 | mww | -23.3358 | 171.8122 | 10.6 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000dge5 | 2021-02-10T21:24:00.831Z | 6.3 | mww | -23.1911 | 171.5827 | 12.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000dgc7 | 2021-02-10T18:36:41.957Z | 6.1 | mww | -22.7173 | 171.2130 | 14.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000dgb4 | 2021-02-10T16:35:22.999Z | 6.1 | mwb | -22.8106 | 171.1730 | 11.7 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000dg77 | 2021-02-10T13:19:55.530Z | 7.7 | mww | -23.0511 | 171.6566 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000dg72 | 2021-02-10T13:01:59.145Z | 6.1 | mww | -22.7415 | 171.6432 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000dg70 | 2021-02-10T12:52:27.224Z | 6.3 | mww | -5.6856 | 101.6495 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 219 km SSW of Bengkulu, Indonesia |
| us6000dg6u | 2021-02-10T12:24:21.500Z | 6.1 | mww | -22.8327 | 171.6556 | 11.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us6000dfad | 2021-02-07T05:45:51.377Z | 6.3 | mww | -3.3226 | 146.1444 | 10.0 | 0 | 1 | 1 | 1 | 0 | 2 | 189 km SW of Lorengau, Papua New Guinea |
| us7000d20e | 2021-01-21T12:23:04.255Z | 7.0 | mww | 4.9931 | 127.5145 | 80.0 | 0 | 1 | 0 | 0 | 0 | 0 | 211 km SE of Pondaguitan, Philippines |
| us7000d030 | 2021-01-14T18:28:18.093Z | 6.2 | mww | -2.9717 | 118.8899 | 18.0 | 0 | 1 | 0 | 0 | 0 | 0 | 32 km S of Mamuju, Indonesia |
| us6000d764 | 2021-01-10T06:48:20.094Z | 6.1 | mww | -16.0347 | 167.8826 | 160.0 | 0 | 5 | 0 | 0 | 0 | 0 | 50 km E of Lakatoro, Vanuatu |
| us6000d6my | 2021-01-08T05:01:04.246Z | 6.1 | mww | -20.7367 | 169.8821 | 113.0 | 0 | 0 | 0 | 0 | 0 | 0 | 146 km SSE of Isangel, Vanuatu |
| us6000d69r | 2021-01-06T20:59:34.315Z | 6.1 | mww | 0.0658 | 122.9487 | 148.0 | 0 | 0 | 0 | 0 | 0 | 0 | 53 km SSW of Gorontalo, Indonesia |
| us7000cfxq | 2020-11-17T01:44:11.421Z | 6.0 | mww | -2.6706 | 99.3227 | 19.0 | 0 | 1 | 0 | 0 | 0 | 0 | 222 km SSW of Padang, Indonesia |
| us6000c6mu | 2020-10-08T07:35:32.524Z | 6.3 | mww | -6.0942 | 146.1738 | 106.0 | 0 | 1 | 0 | 0 | 0 | 0 | 40 km ENE of Kainantu, Papua New Guinea |
| us6000c3td | 2020-10-01T10:34:45.149Z | 6.1 | mww | -5.9961 | 148.6656 | 74.0 | 0 | 1 | 0 | 0 | 0 | 0 | 100 km WNW of Kandrian, Papua New Guinea |
| us7000bj6y | 2020-09-07T06:12:39.688Z | 6.2 | mww | -17.1102 | 168.5034 | 10.0 | 0 | 5 | 0 | 0 | 0 | 0 | 72 km NNE of Port-Vila, Vanuatu |
| us7000birm | 2020-09-06T02:59:16.073Z | 6.2 | mww | -17.1562 | 167.5321 | 10.0 | 0 | 5 | 0 | 0 | 0 | 0 | 104 km NW of Port-Vila, Vanuatu |
| us7000bcty | 2020-08-25T19:08:52.908Z | 6.2 | mww | -5.5454 | 151.8365 | 22.0 | 0 | 1 | 0 | 0 | 0 | 0 | 141 km SSW of Kokopo, Papua New Guinea |
| us7000bctq | 2020-08-25T19:02:58.437Z | 6.0 | mww | -5.5579 | 151.8638 | 23.0 | 0 | 1 | 0 | 0 | 0 | 0 | 141 km SSW of Kokopo, Papua New Guinea |
| us6000bi4p | 2020-08-21T04:09:51.930Z | 6.9 | mww | -6.7100 | 123.4649 | 624.0 | 0 | 1 | 0 | 0 | 0 | 0 | 222 km SSE of Katabu, Indonesia |
| us6000bgvu | 2020-08-18T22:29:24.731Z | 6.9 | mww | -4.2069 | 101.2411 | 26.0 | 0 | 0 | 0 | 0 | 0 | 0 | 122 km WSW of Bengkulu, Indonesia |
| us6000bgvl | 2020-08-18T22:23:59.497Z | 6.8 | mww | -4.3217 | 101.1347 | 22.0 | 0 | 0 | 0 | 0 | 0 | 0 | 138 km WSW of Bengkulu, Indonesia |
| us6000b9mv | 2020-08-05T12:05:36.589Z | 6.4 | mww | -16.0944 | 168.0650 | 181.9 | 0 | 5 | 0 | 0 | 0 | 0 | 69 km E of Lakatoro, Vanuatu |
| us6000b84f | 2020-08-01T19:22:05.163Z | 6.1 | mww | -3.1951 | 148.6496 | 10.0 | 0 | 1 | 1 | 1 | 0 | 4 | 199 km SE of Lorengau, Papua New Guinea |
| us7000aq3e | 2020-07-17T02:50:22.178Z | 7.0 | mww | -7.8360 | 147.7704 | 73.0 | 0 | 2 | 0 | 0 | 0 | 0 | 114 km NNW of Popondetta, Papua New Guinea |
| us7000aj3w | 2020-07-06T22:54:47.538Z | 6.6 | mww | -5.6023 | 110.6893 | 533.8 | 0 | 2 | 0 | 0 | 0 | 0 | Java Sea |
| us6000ah1z | 2020-06-23T07:43:29.219Z | 6.0 | mww | 0.0368 | 123.7866 | 109.0 | 0 | 0 | 0 | 0 | 0 | 0 | 97 km SE of Gorontalo, Indonesia |
| us6000a5r3 | 2020-06-04T08:49:40.397Z | 6.4 | mww | 2.9110 | 128.2480 | 112.9 | 0 | 0 | 0 | 0 | 0 | 0 | 133 km NNE of Tobelo, Indonesia |
| us60009zv5 | 2020-05-27T07:09:09.853Z | 6.2 | mww | -17.5304 | 167.8743 | 9.7 | 0 | 5 | 0 | 0 | 0 | 0 | 51 km WNW of Port-Vila, Vanuatu |
| us70009f12 | 2020-05-12T22:41:12.177Z | 6.6 | mww | -12.0665 | 166.6485 | 107.0 | 0 | 0 | 0 | 0 | 0 | 0 | 175 km SSE of Lata, Solomon Islands |
| us70009bn4 | 2020-05-07T11:21:20.152Z | 6.1 | mww | -4.4643 | 154.7410 | 471.2 | 0 | 1 | 0 | 0 | 0 | 0 | 215 km NNW of Arawa, Papua New Guinea |
| us70009b14 | 2020-05-06T13:53:55.940Z | 6.8 | mww | -6.7761 | 129.7852 | 96.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us60009c06 | 2020-04-25T02:53:06.698Z | 6.1 | mww | -6.5337 | 154.2347 | 19.0 | 0 | 0 | 0 | 0 | 0 | 0 | 140 km W of Panguna, Papua New Guinea |
| us70008peg | 2020-04-05T18:37:10.876Z | 6.0 | mww | 1.3950 | 126.4381 | 42.0 | 0 | 0 | 0 | 0 | 0 | 0 | 124 km WNW of Ternate, Indonesia |
| us60008hzl | 2020-03-18T17:45:39.299Z | 6.2 | mww | -11.0521 | 115.1378 | 20.7 | 0 | 1 | 0 | 0 | 0 | 0 | 249 km S of Nusa Dua, Indonesia |
| us60008hkg | 2020-03-18T03:13:45.742Z | 6.1 | mww | -13.1364 | 167.0277 | 176.0 | 0 | 0 | 0 | 0 | 0 | 0 | 99 km NW of Sola, Vanuatu |
| us600084gu | 2020-02-26T07:33:12.952Z | 6.0 | mww | -7.4887 | 131.1196 | 54.0 | 0 | 0 | 0 | 0 | 0 | 0 | 273 km SW of Tual, Indonesia |
| us70007lwy | 2020-02-09T06:04:29.967Z | 6.1 | mww | -5.4925 | 152.1522 | 34.0 | 0 | 1 | 0 | 0 | 0 | 0 | 127 km S of Kokopo, Papua New Guinea |
| us70007j6z | 2020-02-05T18:12:37.734Z | 6.2 | mww | -6.0817 | 113.0778 | 592.4 | 0 | 1 | 0 | 0 | 0 | 0 | 113 km NNE of Bangkalan, Indonesia |
| us60007j2w | 2020-01-29T13:49:49.744Z | 6.0 | mww | -10.4180 | 161.2756 | 85.0 | 0 | 1 | 1 | 1 | 0 | 2 | 70 km W of Kirakira, Solomon Islands |
| us60007gyx | 2020-01-27T05:02:01.704Z | 6.3 | mww | -10.0929 | 161.0606 | 21.0 | 0 | 1 | 1 | 1 | 0 | 2 | 102 km WNW of Kirakira, Solomon Islands |
| us60007arp | 2020-01-19T16:58:20.002Z | 6.1 | mww | -0.1042 | 123.8025 | 121.7 | 0 | 0 | 0 | 0 | 0 | 0 | 108 km SE of Gorontalo, Indonesia |
| us60007a3h | 2020-01-18T16:38:14.301Z | 6.0 | mww | -2.8405 | 139.3363 | 44.0 | 0 | 0 | 0 | 0 | 0 | 0 | 146 km W of Abepura, Indonesia |
| us70006vvr | 2020-01-07T19:11:35.665Z | 6.0 | mww | -5.2046 | 151.2659 | 117.0 | 0 | 1 | 0 | 0 | 0 | 0 | 130 km ENE of Kimbe, Papua New Guinea |
| us70006vkq | 2020-01-07T06:05:19.759Z | 6.3 | mww | 2.3481 | 96.3575 | 17.0 | 0 | 0 | 0 | 0 | 0 | 0 | 14 km S of Sinabang, Indonesia |
| us60006rem | 2019-12-14T04:57:34.937Z | 6.0 | mww | -14.3628 | 167.7089 | 7.5 | 0 | 0 | 0 | 0 | 0 | 0 | 56 km SSE of Sola, Vanuatu |
| us60006m2j | 2019-12-04T20:10:03.595Z | 6.0 | mww | -19.0677 | 169.5748 | 266.0 | 0 | 5 | 1 | 1 | 0 | 2 | 60 km NNE of Isangel, Vanuatu |
| us70006c6w | 2019-11-23T12:11:15.564Z | 6.2 | mww | 1.6436 | 132.8148 | 5.0 | 0 | 0 | 0 | 0 | 0 | 0 | 241 km SE of Tobi Village, Palau |
| us60006bpw | 2019-11-14T21:12:54.753Z | 6.0 | mww | 1.5361 | 126.4161 | 23.0 | 0 | 0 | 0 | 0 | 0 | 0 | 135 km NW of Ternate, Indonesia |
| us60006bjl | 2019-11-14T16:17:40.578Z | 7.1 | mww | 1.6213 | 126.4156 | 33.0 | 0 | 0 | 0 | 0 | 0 | 0 | 141 km NW of Ternate, Indonesia |
| us700063sp | 2019-11-06T00:39:09.303Z | 6.0 | mww | -13.7208 | 167.8086 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | Vanuatu |
| us700063rx | 2019-11-05T23:17:26.588Z | 6.0 | mww | -13.7988 | 167.7494 | 19.0 | 0 | 0 | 0 | 0 | 0 | 0 | 23 km ENE of Sola, Vanuatu |
| us70005wj6 | 2019-10-21T02:52:29.674Z | 6.4 | mww | -19.0184 | 169.4883 | 231.0 | 0 | 5 | 1 | 1 | 0 | 2 | 61 km NNE of Isangel, Vanuatu |
| us70005lfd | 2019-09-25T23:46:43.543Z | 6.5 | mww | -3.4528 | 128.3699 | 12.3 | 0 | 1 | 0 | 0 | 0 | 0 | 33 km NE of Ambon, Indonesia |
| us60005kta | 2019-09-19T07:06:33.291Z | 6.1 | mww | -6.0708 | 111.8422 | 610.0 | 0 | 2 | 0 | 0 | 0 | 0 | 81 km NNE of Lasem, Indonesia |
| us700057v4 | 2019-08-24T15:51:27.119Z | 6.0 | mww | -14.3090 | 167.1897 | 115.0 | 0 | 0 | 0 | 0 | 0 | 0 | 61 km SW of Sola, Vanuatu |
| us600057xt | 2019-08-21T14:28:25.652Z | 6.0 | mww | -50.3302 | 139.3240 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | western Indian-Antarctic Ridge |
| us600057ee | 2019-08-20T13:03:52.633Z | 6.0 | mww | -11.3683 | 166.2912 | 37.0 | 0 | 0 | 0 | 0 | 0 | 0 | Santa Cruz Islands |
| us60004zhq | 2019-08-02T12:03:27.001Z | 6.9 | mww | -7.2822 | 104.7907 | 49.0 | 0 | 2 | 0 | 0 | 0 | 0 | 152 km SW of Labuan, Indonesia |
| us60004xz4 | 2019-07-31T15:02:33.853Z | 6.6 | mww | -16.1985 | 167.9982 | 181.0 | 0 | 5 | 1 | 1 | 0 | 2 | 63 km E of Lakatoro, Vanuatu |
| us70004kfs | 2019-07-15T08:21:34.171Z | 6.3 | mww | -5.9707 | 149.4881 | 42.0 | 0 | 1 | 0 | 0 | 0 | 0 | 26 km NNW of Kandrian, Papua New Guinea |
| us70004jyv | 2019-07-14T09:10:51.523Z | 7.2 | mww | -0.5858 | 128.0340 | 19.0 | 0 | 0 | 0 | 0 | 0 | 0 | 155 km SSE of Sofifi, Indonesia |
| us70004jxe | 2019-07-14T05:39:23.420Z | 6.6 | mww | -18.2242 | 120.3584 | 10.0 | 0 | 2 | 1 | 1 | 0 | 2 | 198 km W of Cable Beach, Australia |
| us70004icj | 2019-07-11T17:08:37.977Z | 6.0 | mww | -4.6408 | 155.2241 | 495.2 | 0 | 0 | 0 | 0 | 0 | 0 | 179 km NNW of Arawa, Papua New Guinea |
| us70004dz3 | 2019-07-07T15:08:40.525Z | 6.9 | mww | 0.5126 | 126.1892 | 35.0 | 0 | 0 | 0 | 0 | 0 | 0 | 136 km WSW of Ternate, Indonesia |
| us70004840 | 2019-07-01T17:13:28.400Z | 6.0 | mww | -15.4403 | 167.5310 | 91.0 | 0 | 5 | 1 | 1 | 0 | 2 | 40 km ENE of Luganville, Vanuatu |
| us600044zz | 2019-06-24T02:53:39.830Z | 7.3 | mww | -6.4078 | 129.1692 | 212.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us600044z4 | 2019-06-24T01:05:29.464Z | 6.1 | mww | -2.7756 | 138.5675 | 28.0 | 0 | 0 | 0 | 0 | 0 | 0 | 230 km W of Abepura, Indonesia |
| us6000434e | 2019-06-19T17:24:48.803Z | 6.3 | mww | -2.2656 | 138.4610 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 244 km W of Abepura, Indonesia |
| us70003n96 | 2019-05-19T14:56:50.691Z | 6.3 | mww | -21.6074 | 169.4692 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | 164 km E of Tadine, New Caledonia |
| us70003n8z | 2019-05-19T14:27:11.826Z | 6.0 | mww | -21.7313 | 169.5758 | 16.0 | 0 | 0 | 0 | 0 | 0 | 0 | 176 km E of Tadine, New Caledonia |
| us70003n4z | 2019-05-19T01:23:29.151Z | 6.3 | mww | -21.6619 | 169.7779 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | 196 km E of Tadine, New Caledonia |
| us70003kyy | 2019-05-14T12:58:25.939Z | 7.6 | mww | -4.0510 | 152.5967 | 10.0 | 0 | 1 | 0 | 0 | 0 | 0 | 48 km NE of Kokopo, Papua New Guinea |
| us70003hqb | 2019-05-06T21:19:37.983Z | 7.1 | mww | -6.9746 | 146.4494 | 146.0 | 0 | 2 | 0 | 0 | 0 | 0 | 32 km NW of Bulolo, Papua New Guinea |
| us70003g5a | 2019-05-03T07:25:31.787Z | 6.2 | mww | -6.9478 | 160.1125 | 27.0 | 0 | 1 | 1 | 1 | 0 | 2 | 144 km NNE of Buala, Solomon Islands |
| us700038m1 | 2019-04-18T14:46:01.733Z | 6.3 | mww | -51.1270 | 139.3210 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | western Indian-Antarctic Ridge |
| us700034zz | 2019-04-12T14:51:31.603Z | 6.0 | mww | -6.4883 | 148.7394 | 30.0 | 0 | 1 | 0 | 0 | 0 | 0 | 94 km WSW of Kandrian, Papua New Guinea |
| us700034xq | 2019-04-12T11:40:49.363Z | 6.8 | mww | -1.8146 | 122.5798 | 15.5 | 0 | 0 | 0 | 0 | 0 | 0 | Sulawesi, Indonesia |
| us2000kbi1 | 2019-04-06T21:55:01.660Z | 6.3 | mww | -6.8285 | 125.0416 | 539.0 | 0 | 0 | 0 | 0 | 0 | 0 | 197 km N of Likisá, Timor Leste |
| us2000k7ks | 2019-03-30T11:20:42.559Z | 6.2 | mww | -5.7003 | 151.1053 | 41.0 | 0 | 1 | 0 | 0 | 0 | 0 | 108 km E of Kimbe, Papua New Guinea |
| us1000jkwi | 2019-03-24T04:37:35.918Z | 6.1 | mww | 1.6601 | 126.3955 | 45.0 | 0 | 0 | 0 | 0 | 0 | 0 | 146 km NW of Ternate, Indonesia |
| us1000jj9r | 2019-03-20T15:23:58.680Z | 6.3 | mww | -15.5965 | 167.6551 | 119.0 | 0 | 5 | 1 | 1 | 0 | 2 | 53 km E of Luganville, Vanuatu |
| us1000jd7d | 2019-03-10T12:48:00.607Z | 6.0 | mww | -10.1317 | 152.0647 | 9.0 | 0 | 0 | 0 | 0 | 0 | 0 | 162 km ENE of Samarai, Papua New Guinea |
| us2000jj68 | 2019-02-17T14:35:55.840Z | 6.4 | mww | -3.3412 | 152.1319 | 368.1 | 0 | 1 | 0 | 0 | 0 | 0 | 95 km N of Rabaul, Papua New Guinea |
| us2000jcbz | 2019-02-02T09:27:36.030Z | 6.0 | mww | -2.8462 | 100.0743 | 20.0 | 0 | 1 | 0 | 0 | 0 | 0 | 170 km WSW of Sungai Penuh, Indonesia |
| us2000j92w | 2019-01-26T03:51:37.870Z | 6.2 | mww | -7.0089 | 156.3207 | 355.0 | 0 | 0 | 0 | 0 | 0 | 0 | 116 km SE of Kieta, Papua New Guinea |
| us2000j73a | 2019-01-22T05:10:03.480Z | 6.3 | mww | -10.4148 | 119.0165 | 24.0 | 0 | 0 | 0 | 0 | 0 | 0 | 160 km WSW of Waingapu, Indonesia |
| us2000j70q | 2019-01-21T23:59:23.860Z | 6.0 | mww | -10.3278 | 119.1521 | 26.0 | 0 | 0 | 0 | 0 | 0 | 0 | 142 km WSW of Waingapu, Indonesia |
| us2000j5qu | 2019-01-18T13:18:31.030Z | 6.0 | mww | -19.2036 | 168.7446 | 38.7 | 0 | 5 | 0 | 0 | 0 | 0 | 67 km WNW of Isangel, Vanuatu |
| us2000j545 | 2019-01-17T15:06:35.650Z | 6.2 | mww | -3.2307 | 146.3889 | 10.0 | 0 | 1 | 1 | 1 | 0 | 2 | 164 km SW of Lorengau, Papua New Guinea |
| us2000j468 | 2019-01-15T18:06:34.300Z | 6.6 | mww | -13.3360 | 166.8752 | 35.0 | 0 | 0 | 0 | 0 | 0 | 0 | 94 km NW of Sola, Vanuatu |
| us2000j0uj | 2019-01-06T17:27:18.980Z | 6.6 | mww | 2.2580 | 126.7580 | 43.2 | 0 | 0 | 0 | 0 | 0 | 0 | Molucca Sea |
| us2000iwat | 2018-12-22T14:25:01.180Z | 6.0 | mww | -13.4000 | 166.8151 | 42.0 | 0 | 0 | 0 | 0 | 0 | 0 | 95 km WNW of Sola, Vanuatu |
| us2000iu2u | 2018-12-16T09:42:37.200Z | 6.1 | mww | -3.9226 | 140.2323 | 62.0 | 0 | 0 | 0 | 0 | 0 | 0 | 153 km SSW of Abepura, Indonesia |
| us1000i2k0 | 2018-12-05T06:43:04.130Z | 6.6 | mww | -22.0629 | 169.7331 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 199 km ESE of Tadine, New Caledonia |
| us1000i2gt | 2018-12-05T04:18:08.420Z | 7.5 | mww | -21.9496 | 169.4266 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 166 km ESE of Tadine, New Caledonia |
| us1000i2gr | 2018-12-05T04:14:36.490Z | 6.3 | mb | -22.0161 | 169.3495 | 10.0 | 0 | 2 | 0 | 0 | 0 | 0 | 160 km ESE of Tadine, New Caledonia |
| us1000hzjp | 2018-12-01T13:27:21.080Z | 6.4 | mww | -7.3841 | 128.7065 | 136.0 | 0 | 0 | 0 | 0 | 0 | 0 | 226 km NE of Lospalos, Timor Leste |
| us1000hsie | 2018-11-16T03:26:55.640Z | 6.2 | mww | -10.5383 | 163.1676 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 136 km E of Kirakira, Solomon Islands |
| us1000hiup | 2018-10-30T02:13:39.480Z | 6.1 | mww | -39.0570 | 174.9584 | 225.5 | 0 | 146 | 0 | 0 | 0 | 0 | 62 km E of Waitara, New Zealand |
| us1000hclz | 2018-10-16T01:03:43.580Z | 6.5 | mww | -21.7427 | 169.5217 | 17.0 | 0 | 0 | 0 | 0 | 0 | 0 | 171 km E of Tadine, New Caledonia |
| us1000hcln | 2018-10-16T00:28:13.060Z | 6.3 | mww | -21.9232 | 169.4869 | 12.0 | 0 | 0 | 0 | 0 | 0 | 0 | 171 km ESE of Tadine, New Caledonia |
| us1000habl | 2018-10-10T22:00:34.500Z | 6.2 | mww | -4.9624 | 151.7231 | 121.0 | 0 | 1 | 0 | 0 | 0 | 0 | 91 km SW of Kokopo, Papua New Guinea |
| us1000haa3 | 2018-10-10T20:48:20.100Z | 7.0 | mww | -5.7012 | 151.2046 | 39.0 | 0 | 1 | 0 | 0 | 0 | 0 | 119 km E of Kimbe, Papua New Guinea |
| us1000ha9t | 2018-10-10T20:45:25.300Z | 6.1 | mb | -5.7433 | 151.3533 | 41.6 | 0 | 1 | 0 | 0 | 0 | 0 | 136 km E of Kimbe, Papua New Guinea |
| us1000ha6q | 2018-10-10T18:44:55.280Z | 6.0 | mww | -7.4525 | 114.4553 | 9.0 | 0 | 2 | 0 | 0 | 0 | 0 | 49 km NE of Panji, Indonesia |
| us1000h5eg | 2018-10-01T23:59:42.740Z | 6.0 | mww | -10.5585 | 120.2424 | 29.0 | 0 | 0 | 0 | 0 | 0 | 0 | 99 km S of Waingapu, Indonesia |
| us1000h3p4 | 2018-09-28T10:02:45.250Z | 7.5 | mww | -0.2559 | 119.8462 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | 72 km N of Palu, Indonesia |
| us1000h3mf | 2018-09-28T06:59:59.740Z | 6.1 | mww | -0.4009 | 119.7705 | 5.0 | 0 | 0 | 0 | 0 | 0 | 0 | 57 km NNW of Palu, Indonesia |
| us2000hfjk | 2018-09-16T21:11:48.820Z | 6.5 | mww | -25.4150 | 178.1991 | 576.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us2000hc1x | 2018-09-10T19:31:37.420Z | 6.3 | mww | -21.9880 | 170.1584 | 12.0 | 0 | 0 | 0 | 0 | 0 | 0 | 240 km ESE of Tadine, New Caledonia |
| us2000hbk9 | 2018-09-09T19:31:35.090Z | 6.5 | mww | -10.0207 | 161.5025 | 68.0 | 0 | 1 | 1 | 1 | 0 | 2 | 66 km NW of Kirakira, Solomon Islands |
| us2000h9e2 | 2018-09-06T15:49:18.710Z | 7.9 | mww | -18.4743 | 179.3502 | 670.8 | 0 | 9 | 1 | 1 | 0 | 2 | 45 km S of Levuka, Fiji |
| us1000gjaz | 2018-08-29T03:51:56.100Z | 7.1 | mww | -22.0295 | 170.1262 | 21.4 | 0 | 0 | 0 | 0 | 0 | 0 | 238 km ESE of Tadine, New Caledonia |
| us1000gii0 | 2018-08-28T07:08:11.360Z | 6.2 | mww | -10.7730 | 124.1871 | 14.0 | 0 | 0 | 0 | 0 | 0 | 0 | 92 km SE of Kupang, Indonesia |
| us1000gf2g | 2018-08-21T22:32:26.470Z | 6.5 | mww | -16.0315 | 168.1428 | 9.0 | 0 | 5 | 0 | 0 | 0 | 0 | 78 km E of Lakatoro, Vanuatu |
| us1000gda5 | 2018-08-19T14:56:27.490Z | 6.9 | mww | -8.3190 | 116.6272 | 21.0 | 0 | 1 | 0 | 0 | 0 | 0 | 20 km NNW of Labuan Lombok, Indonesia |
| us1000gcvr | 2018-08-19T04:10:22.640Z | 6.3 | mww | -8.3366 | 116.5993 | 16.0 | 0 | 1 | 0 | 0 | 0 | 0 | 19 km NNW of Labuan Lombok, Indonesia |
| us1000gbi4 | 2018-08-17T15:35:01.890Z | 6.5 | mww | -7.3718 | 119.8017 | 529.0 | 0 | 1 | 0 | 0 | 0 | 0 | 124 km N of Labuan Bajo, Indonesia |
| us1000g3ub | 2018-08-05T11:46:38.630Z | 6.9 | mww | -8.2581 | 116.4375 | 34.0 | 0 | 1 | 0 | 0 | 0 | 0 | 36 km NW of Labuan Lombok, Indonesia |
| us2000ggbs | 2018-07-28T22:47:38.740Z | 6.4 | mww | -8.2395 | 116.5080 | 14.0 | 0 | 1 | 0 | 0 | 0 | 0 | 33 km NNW of Labuan Lombok, Indonesia |
| us2000gg76 | 2018-07-28T17:07:23.380Z | 6.0 | mww | -7.1039 | 122.7263 | 578.2 | 0 | 1 | 0 | 0 | 0 | 0 | 177 km NNE of Maumere, Indonesia |
| usd00090uc | 2018-07-19T18:30:32.710Z | 6.0 | mww | -6.1139 | 148.7302 | 29.6 | 0 | 1 | 0 | 0 | 0 | 0 | 91 km W of Kandrian, Papua New Guinea |
| us2000g6uy | 2018-07-17T07:02:53.020Z | 6.0 | mww | -11.5936 | 166.4320 | 38.0 | 0 | 0 | 0 | 0 | 0 | 0 | 118 km SE of Lata, Solomon Islands |
| us2000g3up | 2018-07-13T09:46:49.070Z | 6.4 | mww | -18.9279 | 169.0467 | 167.0 | 0 | 5 | 0 | 0 | 0 | 0 | 72 km NNW of Isangel, Vanuatu |
| us1000ey2i | 2018-06-21T21:13:32.660Z | 6.1 | mww | -17.7905 | 168.0568 | 28.0 | 0 | 5 | 0 | 0 | 0 | 0 | 27 km WSW of Port-Vila, Vanuatu |
| us1000e17w | 2018-05-09T07:57:54.950Z | 6.0 | mww | -5.8822 | 151.7836 | 9.0 | 0 | 1 | 0 | 0 | 0 | 0 | 178 km SSW of Kokopo, Papua New Guinea |
| us2000e0mq | 2018-04-15T19:30:43.200Z | 6.0 | mww | 1.4083 | 126.8759 | 34.0 | 0 | 0 | 0 | 0 | 0 | 0 | 88 km NW of Ternate, Indonesia |
| us2000dvwq | 2018-04-07T05:48:40.010Z | 6.3 | mww | -5.8382 | 142.5314 | 18.1 | 0 | 0 | 0 | 0 | 0 | 0 | 45 km W of Tari, Papua New Guinea |
| us1000db40 | 2018-03-29T21:25:36.790Z | 6.9 | mww | -5.5321 | 151.4999 | 35.0 | 0 | 1 | 0 | 0 | 0 | 0 | 150 km E of Kimbe, Papua New Guinea |
| us1000d937 | 2018-03-26T09:51:00.430Z | 6.7 | mww | -5.5024 | 151.4025 | 40.0 | 0 | 1 | 0 | 0 | 0 | 0 | 140 km E of Kimbe, Papua New Guinea |
| us1000d8xh | 2018-03-25T20:14:47.690Z | 6.4 | mww | -6.6343 | 129.8172 | 169.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us1000d8ny | 2018-03-24T19:58:33.380Z | 6.0 | mww | -45.7783 | 96.0692 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast Indian Ridge |
| us1000d8k9 | 2018-03-24T11:23:32.050Z | 6.3 | mww | -5.4959 | 151.4971 | 33.0 | 0 | 1 | 0 | 0 | 0 | 0 | 150 km E of Kimbe, Papua New Guinea |
| us1000d1kv | 2018-03-08T17:39:51.100Z | 6.8 | mww | -4.3762 | 153.1996 | 22.9 | 0 | 1 | 0 | 0 | 0 | 0 | 103 km E of Kokopo, Papua New Guinea |
| us2000dcx1 | 2018-03-06T14:13:07.650Z | 6.7 | mww | -6.3043 | 142.6116 | 20.5 | 0 | 0 | 0 | 0 | 0 | 0 | 62 km SW of Tari, Papua New Guinea |
| us2000dc52 | 2018-03-04T19:56:17.890Z | 6.0 | mww | -6.3310 | 142.5994 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 66 km SW of Tari, Papua New Guinea |
| us2000d90d | 2018-02-28T02:45:45.430Z | 6.1 | mww | -6.1696 | 142.4681 | 16.0 | 0 | 0 | 0 | 0 | 0 | 0 | 63 km SW of Tari, Papua New Guinea |
| us2000d867 | 2018-02-26T15:18:00.280Z | 6.3 | mww | -6.5052 | 143.2550 | 19.0 | 0 | 0 | 0 | 0 | 0 | 0 | 59 km SW of Mendi, Papua New Guinea |
| us2000d855 | 2018-02-26T13:34:53.530Z | 6.1 | mww | -2.7774 | 126.6859 | 9.0 | 0 | 1 | 0 | 0 | 0 | 0 | 194 km WNW of Ambon, Indonesia |
| us2000d7q6 | 2018-02-25T17:44:44.140Z | 7.5 | mww | -6.0699 | 142.7536 | 25.2 | 0 | 0 | 0 | 0 | 0 | 0 | 32 km SW of Tari, Papua New Guinea |
| us2000cq5t | 2018-01-26T22:47:57.760Z | 6.3 | mww | -3.5138 | 145.8477 | 10.0 | 0 | 1 | 1 | 1 | 0 | 2 | 188 km N of Madang, Papua New Guinea |
| us2000c4v8 | 2017-12-15T16:47:58.230Z | 6.5 | mww | -7.4921 | 108.1743 | 90.0 | 0 | 3 | 0 | 0 | 0 | 0 | 12 km SSW of Kawalu, Indonesia |
| us1000bjph | 2017-12-01T02:49:58.490Z | 6.0 | mww | -6.1346 | 147.6564 | 34.0 | 0 | 1 | 0 | 0 | 0 | 0 | 51 km NNW of Finschhafen, Papua New Guinea |
| us2000burc | 2017-11-27T07:11:11.620Z | 6.0 | mww | -4.5746 | 153.2269 | 54.0 | 0 | 1 | 0 | 0 | 0 | 0 | 109 km ESE of Kokopo, Papua New Guinea |
| us2000brnd | 2017-11-20T00:09:23.730Z | 6.0 | mww | -21.4848 | 168.8088 | 10.0 | 0 | 3 | 0 | 0 | 0 | 0 | 96 km E of Tadine, New Caledonia |
| us2000brlf | 2017-11-19T22:43:29.250Z | 7.0 | mww | -21.3246 | 168.6715 | 10.0 | 0 | 3 | 0 | 0 | 0 | 0 | 85 km ENE of Tadine, New Caledonia |
| us2000brgk | 2017-11-19T15:09:02.880Z | 6.6 | mww | -21.5027 | 168.5984 | 13.0 | 0 | 3 | 0 | 0 | 0 | 0 | 74 km E of Tadine, New Caledonia |
| us2000brbk | 2017-11-19T09:25:48.730Z | 6.3 | mww | -21.6377 | 168.6729 | 14.0 | 0 | 3 | 0 | 0 | 0 | 0 | 82 km E of Tadine, New Caledonia |
| us2000bk15 | 2017-11-07T21:26:38.480Z | 6.5 | mww | -4.2433 | 143.4846 | 110.6 | 0 | 0 | 0 | 0 | 0 | 0 | 67 km WSW of Angoram, Papua New Guinea |
| us1000azjt | 2017-11-01T02:23:57.670Z | 6.6 | mww | -21.6484 | 168.8585 | 22.0 | 0 | 3 | 0 | 0 | 0 | 0 | 101 km E of Tadine, New Caledonia |
| us1000azi3 | 2017-11-01T00:09:30.120Z | 6.1 | mww | -21.7278 | 168.9342 | 11.0 | 0 | 3 | 0 | 0 | 0 | 0 | 110 km E of Tadine, New Caledonia |
| us1000ayz8 | 2017-10-31T11:50:48.370Z | 6.1 | mww | -3.7449 | 127.7517 | 6.0 | 0 | 1 | 0 | 0 | 0 | 0 | 48 km W of Ambon, Indonesia |
| us1000aytk | 2017-10-31T00:42:08.720Z | 6.7 | mww | -21.6971 | 169.1485 | 24.0 | 0 | 3 | 0 | 0 | 0 | 0 | 132 km E of Tadine, New Caledonia |
| us1000aw8q | 2017-10-24T10:47:47.860Z | 6.7 | mww | -7.2168 | 123.0735 | 553.8 | 0 | 1 | 0 | 0 | 0 | 0 | 181 km NNE of Maumere, Indonesia |
| us2000as2f | 2017-09-20T20:09:49.610Z | 6.4 | mww | -18.7854 | 169.0946 | 197.0 | 0 | 5 | 1 | 1 | 0 | 2 | 85 km NNW of Isangel, Vanuatu |
| us2000arel | 2017-09-20T01:43:25.980Z | 6.1 | mww | -50.7087 | 162.6317 | 8.0 | 0 | 0 | 0 | 0 | 0 | 0 | Auckland Islands, New Zealand region |
| us2000adjh | 2017-08-31T17:06:55.750Z | 6.3 | mww | -1.1590 | 99.6881 | 43.1 | 0 | 1 | 0 | 0 | 0 | 0 | 76 km SW of Pariaman, Indonesia |
| us2000ac7a | 2017-08-27T04:17:51.000Z | 6.3 | mww | -1.4525 | 148.0800 | 8.0 | 0 | 1 | 1 | 1 | 0 | 2 | 110 km NE of Lorengau, Papua New Guinea |
| us2000a7q2 | 2017-08-13T03:08:10.560Z | 6.4 | mww | -3.7682 | 101.6228 | 31.0 | 0 | 0 | 0 | 0 | 0 | 0 | 71 km W of Bengkulu, Indonesia |
| us20009vvi | 2017-07-13T03:36:08.640Z | 6.4 | mww | -4.7787 | 153.2109 | 34.0 | 0 | 1 | 0 | 0 | 0 | 0 | 115 km ESE of Kokopo, Papua New Guinea |
| us100098qm | 2017-07-11T07:00:01.190Z | 6.6 | mww | -49.4837 | 164.0157 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | Auckland Islands, New Zealand region |
| us1000954z | 2017-06-29T07:03:11.040Z | 6.0 | mww | -31.1253 | 179.9257 | 404.8 | 0 | 1 | 0 | 0 | 0 | 0 | Kermadec Islands region |
| us20009nc2 | 2017-06-17T22:26:02.010Z | 6.1 | mww | -24.0927 | 179.6041 | 511.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us10008w1z | 2017-05-29T14:35:21.510Z | 6.6 | mww | -1.2923 | 120.4313 | 12.0 | 0 | 0 | 0 | 0 | 0 | 0 | 37 km WNW of Poso, Indonesia |
| us10008sjn | 2017-05-15T13:22:38.630Z | 6.2 | mww | -4.0220 | 152.4781 | 10.0 | 0 | 1 | 0 | 0 | 0 | 0 | 40 km ENE of Rabaul, Papua New Guinea |
| us10008qsb | 2017-05-09T13:52:10.940Z | 6.8 | mww | -14.5884 | 167.3767 | 169.0 | 0 | 0 | 0 | 0 | 0 | 0 | 59 km NNE of Port-Olry, Vanuatu |
| us20008t6m | 2017-03-19T15:43:25.690Z | 6.0 | mww | -8.1364 | 160.7536 | 8.4 | 0 | 1 | 1 | 1 | 0 | 2 | 70 km N of Auki, Solomon Islands |
| us1000876f | 2017-03-05T22:47:53.970Z | 6.3 | mww | -5.9945 | 149.3619 | 37.0 | 0 | 1 | 0 | 0 | 0 | 0 | 31 km NW of Kandrian, Papua New Guinea |
| us100086x7 | 2017-03-04T02:58:20.280Z | 6.1 | mww | -7.3277 | 155.7480 | 17.0 | 0 | 0 | 0 | 0 | 0 | 0 | 115 km SSE of Panguna, Papua New Guinea |
| us10007uph | 2017-01-22T04:30:22.960Z | 7.9 | mww | -6.2464 | 155.1718 | 135.0 | 0 | 0 | 0 | 0 | 0 | 0 | 35 km WNW of Panguna, Papua New Guinea |
| us10007u7n | 2017-01-19T23:04:21.150Z | 6.5 | mww | -10.3506 | 161.3355 | 36.0 | 0 | 1 | 1 | 1 | 0 | 2 | 65 km W of Kirakira, Solomon Islands |
| us10007sd4 | 2017-01-10T15:27:14.780Z | 6.3 | mww | -10.1132 | 161.0271 | 26.0 | 0 | 1 | 1 | 1 | 0 | 2 | 104 km WNW of Kirakira, Solomon Islands |
| us10007s9c | 2017-01-10T06:13:48.140Z | 7.3 | mww | 4.4782 | 122.6171 | 627.2 | 0 | 0 | 0 | 0 | 0 | 0 | 189 km SSE of Tabiauan, Philippines |
| us10007pjt | 2017-01-03T22:40:12.570Z | 6.0 | mww | -19.1207 | 176.1875 | 10.0 | 0 | 5 | 1 | 1 | 0 | 1 | 195 km SW of Nadi, Fiji |
| us10007pj6 | 2017-01-03T21:52:30.670Z | 6.9 | mww | -19.3733 | 176.0518 | 12.0 | 0 | 5 | 1 | 1 | 0 | 2 | 225 km SW of Nadi, Fiji |
| us10007p7m | 2017-01-02T13:14:02.830Z | 6.3 | mww | -23.2513 | 179.2383 | 551.6 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us10007nl0 | 2016-12-29T22:30:19.300Z | 6.3 | mww | -9.0279 | 118.6639 | 79.0 | 0 | 0 | 0 | 0 | 0 | 0 | 58 km SSE of Dompu, Indonesia |
| us10007mf5 | 2016-12-24T01:32:16.040Z | 6.0 | mww | -5.2453 | 153.5754 | 35.0 | 0 | 1 | 0 | 0 | 0 | 0 | 175 km SE of Kokopo, Papua New Guinea |
| us10007lkw | 2016-12-21T00:17:14.990Z | 6.7 | mww | -7.5082 | 127.9206 | 152.0 | 0 | 0 | 0 | 0 | 0 | 0 | 151 km NE of Lospalos, Timor Leste |
| us200082tk | 2016-12-20T12:33:14.240Z | 6.0 | mww | -10.1785 | 160.9149 | 10.0 | 0 | 1 | 1 | 1 | 0 | 2 | 114 km WNW of Kirakira, Solomon Islands |
| us200082pp | 2016-12-20T04:21:29.150Z | 6.4 | mww | -10.1750 | 161.2271 | 20.0 | 0 | 1 | 1 | 1 | 0 | 2 | 81 km WNW of Kirakira, Solomon Islands |
| us200081w0 | 2016-12-17T11:27:36.170Z | 6.3 | mww | -5.6291 | 154.0216 | 8.4 | 0 | 1 | 0 | 0 | 0 | 0 | 178 km WNW of Panguna, Papua New Guinea |
| us200081v8 | 2016-12-17T10:51:10.500Z | 7.9 | mww | -4.5049 | 153.5216 | 94.5 | 0 | 1 | 0 | 0 | 0 | 0 | 140 km E of Kokopo, Papua New Guinea |
| us20007ztn | 2016-12-10T16:24:34.970Z | 6.0 | mww | -5.6593 | 154.4734 | 142.6 | 0 | 0 | 0 | 0 | 0 | 0 | 133 km WNW of Panguna, Papua New Guinea |
| us20007zlq | 2016-12-09T19:10:06.840Z | 6.9 | mww | -10.7490 | 161.1316 | 19.7 | 0 | 1 | 1 | 1 | 0 | 2 | 92 km WSW of Kirakira, Solomon Islands |
| us20007zbn | 2016-12-08T21:56:07.500Z | 6.5 | mww | -10.8416 | 161.3137 | 12.3 | 0 | 1 | 1 | 1 | 0 | 2 | 79 km WSW of Kirakira, Solomon Islands |
| us20007z80 | 2016-12-08T17:38:46.280Z | 7.8 | mww | -10.6812 | 161.3273 | 40.0 | 0 | 1 | 1 | 1 | 0 | 2 | 69 km WSW of Kirakira, Solomon Islands |
| us10007ev8 | 2016-12-05T01:13:04.880Z | 6.3 | mww | -7.3158 | 123.3802 | 526.0 | 0 | 1 | 0 | 0 | 0 | 0 | 193 km NE of Maumere, Indonesia |
| us100077hw | 2016-11-14T00:34:22.610Z | 6.5 | mww | -42.6058 | 173.2543 | 9.0 | 0 | 49 | 0 | 0 | 0 | 0 | 74 km NE of Amberley, New Zealand |
| us100077aj | 2016-11-13T13:31:25.660Z | 6.2 | mww | -42.3093 | 173.6961 | 2.1 | 0 | 55 | 0 | 0 | 0 | 0 | 90 km SSW of Blenheim, New Zealand |
| us1000779b | 2016-11-13T11:52:45.010Z | 6.1 | mww | -42.1762 | 173.6227 | 14.0 | 0 | 55 | 0 | 0 | 0 | 0 | 78 km SSW of Blenheim, New Zealand |
| us10007795 | 2016-11-13T11:32:06.540Z | 6.5 | mww | -42.3205 | 173.6694 | 10.0 | 0 | 54 | 0 | 0 | 0 | 0 | 92 km SSW of Blenheim, New Zealand |
| us1000778i | 2016-11-13T11:02:56.340Z | 7.8 | mww | -42.7373 | 173.0540 | 15.1 | 0 | 48 | 0 | 0 | 0 | 0 | 53 km NNE of Amberley, New Zealand |
| us100073jd | 2016-11-01T19:03:30.100Z | 6.0 | mww | -6.1039 | 148.6588 | 52.0 | 0 | 1 | 0 | 0 | 0 | 0 | 99 km W of Kandrian, Papua New Guinea |
| us20007f7j | 2016-10-19T00:26:01.090Z | 6.6 | mww | -4.8626 | 108.1627 | 614.0 | 0 | 2 | 0 | 0 | 0 | 0 | 161 km NNE of Pamanukan, Indonesia |
| us20007ept | 2016-10-17T06:14:58.270Z | 6.8 | mww | -6.0033 | 148.8871 | 42.0 | 0 | 1 | 0 | 0 | 0 | 0 | 76 km WNW of Kandrian, Papua New Guinea |
| us20007ebu | 2016-10-15T08:03:38.150Z | 6.3 | mww | -4.2735 | 150.3606 | 442.0 | 0 | 1 | 0 | 0 | 0 | 0 | 143 km N of Kimbe, Papua New Guinea |
| us10006qas | 2016-09-17T01:20:17.940Z | 6.0 | mww | -2.0829 | 140.5718 | 9.0 | 0 | 0 | 0 | 0 | 0 | 0 | 52 km NNW of Jayapura, Indonesia |
| us10006pfn | 2016-09-14T07:25:00.070Z | 6.0 | mww | -9.3290 | 159.1673 | 14.0 | 0 | 1 | 1 | 1 | 0 | 2 | 72 km NW of Malango, Solomon Islands |
| us10006n6r | 2016-09-08T21:46:20.100Z | 6.1 | mww | -54.6136 | 158.7126 | 10.0 | 0 | 1 | 1 | 1 | 0 | 2 | Macquarie Island region |
| us10006jd4 | 2016-09-01T17:14:06.060Z | 6.1 | mww | -37.0522 | 178.9291 | 13.7 | 0 | 47 | 0 | 0 | 0 | 0 | 179 km NE of Opotiki, New Zealand |
| us10006jbi | 2016-09-01T16:37:57.300Z | 7.0 | mww | -37.3586 | 179.1461 | 19.0 | 0 | 48 | 0 | 0 | 0 | 0 | 175 km NE of Gisborne, New Zealand |
| us10006iy0 | 2016-08-31T03:11:34.420Z | 6.8 | mww | -3.6849 | 152.7915 | 476.0 | 0 | 1 | 0 | 0 | 0 | 0 | 90 km NE of Rabaul, Papua New Guinea |
| us10006g2n | 2016-08-23T19:39:44.580Z | 6.0 | mww | -7.2872 | 122.4345 | 533.0 | 0 | 1 | 0 | 0 | 0 | 0 | 149 km N of Maumere, Indonesia |
| us10006d5h | 2016-08-12T01:26:36.280Z | 7.2 | mww | -22.4765 | 173.1167 | 16.4 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| us20006hkb | 2016-07-25T19:38:45.560Z | 6.4 | mww | -2.9690 | 148.0345 | 14.0 | 0 | 1 | 1 | 1 | 0 | 2 | 133 km SE of Lorengau, Papua New Guinea |
| us20006g6l | 2016-07-20T15:13:16.520Z | 6.1 | mww | -18.9285 | 169.0547 | 167.0 | 0 | 5 | 1 | 1 | 0 | 2 | 71 km NNW of Isangel, Vanuatu |
| us10005yp3 | 2016-06-30T11:30:33.050Z | 6.0 | mww | -16.0558 | 167.4701 | 27.0 | 0 | 5 | 1 | 1 | 0 | 2 | 7 km NE of Lakatoro, Vanuatu |
| us200065sc | 2016-06-21T17:12:07.370Z | 6.3 | mww | -3.4199 | 151.8796 | 354.0 | 0 | 1 | 0 | 0 | 0 | 0 | 91 km NNW of Rabaul, Papua New Guinea |
| us200065g0 | 2016-06-20T03:50:55.240Z | 6.0 | mww | -20.2072 | 168.7595 | 15.0 | 0 | 5 | 1 | 1 | 0 | 2 | 91 km SW of Isangel, Vanuatu |
| us200065d1 | 2016-06-19T09:47:23.600Z | 6.3 | mww | -20.2793 | 169.0737 | 13.0 | 0 | 5 | 1 | 1 | 0 | 2 | 84 km SSW of Isangel, Vanuatu |
| us200064bb | 2016-06-14T13:49:22.630Z | 6.2 | mww | -18.7609 | 168.8279 | 111.0 | 0 | 5 | 1 | 1 | 0 | 2 | 98 km NNW of Isangel, Vanuatu |
| us200063dk | 2016-06-10T04:17:44.840Z | 6.2 | mww | -8.6757 | 160.5590 | 30.4 | 0 | 1 | 1 | 1 | 0 | 2 | 18 km WNW of Auki, Solomon Islands |
| us200062zs | 2016-06-09T04:13:08.130Z | 6.1 | mww | -11.2487 | 116.2669 | 19.0 | 0 | 0 | 0 | 0 | 0 | 0 | 279 km S of Lembar, Indonesia |
| us200062l9 | 2016-06-07T19:15:15.330Z | 6.3 | mww | 1.2789 | 126.3712 | 31.0 | 0 | 0 | 0 | 0 | 0 | 0 | 125 km WNW of Ternate, Indonesia |
| us2000626m | 2016-06-05T16:25:33.540Z | 6.3 | mww | -4.5870 | 125.6264 | 429.6 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| us20005zt1 | 2016-06-01T22:56:00.800Z | 6.6 | mww | -2.0967 | 100.6654 | 50.0 | 0 | 1 | 0 | 0 | 0 | 0 | 80 km W of Sungai Penuh, Indonesia |
| us10005iyk | 2016-05-20T18:14:04.670Z | 6.0 | mww | -25.5655 | 129.8841 | 10.0 | 0 | 2 | 2 | 2 | 0 | 4 | 116 km WSW of Yulara, Australia |
| us10005c88 | 2016-04-28T19:33:24.070Z | 7.0 | mww | -16.0429 | 167.3786 | 24.0 | 0 | 5 | 1 | 1 | 0 | 2 | 3 km NW of Norsup, Vanuatu |
| us20005i6p | 2016-04-14T21:50:27.680Z | 6.4 | mww | -14.5284 | 166.4334 | 16.0 | 0 | 0 | 0 | 0 | 0 | 0 | 89 km NW of Port-Olry, Vanuatu |
| us20005fzn | 2016-04-07T03:32:53.500Z | 6.7 | mww | -13.9805 | 166.5943 | 27.6 | 0 | 0 | 0 | 0 | 0 | 0 | 104 km W of Sola, Vanuatu |
| us20005fv5 | 2016-04-06T14:45:29.620Z | 6.1 | mww | -8.2036 | 107.3857 | 29.0 | 0 | 2 | 0 | 0 | 0 | 0 | 111 km S of Banjar, Indonesia |
| us20005fsi | 2016-04-06T06:58:48.210Z | 6.7 | mww | -14.0683 | 166.6245 | 24.0 | 0 | 0 | 0 | 0 | 0 | 0 | 102 km WSW of Sola, Vanuatu |
| us20005e8t | 2016-04-03T08:23:52.320Z | 6.9 | mww | -14.3235 | 166.8551 | 26.0 | 0 | 0 | 0 | 0 | 0 | 0 | 82 km NNW of Port-Olry, Vanuatu |
| us20005e01 | 2016-04-01T19:24:55.370Z | 6.2 | mww | -3.3585 | 144.8870 | 6.0 | 0 | 0 | 0 | 0 | 0 | 0 | 119 km NE of Angoram, Papua New Guinea |
| us10004u1y | 2016-03-02T12:49:48.110Z | 7.8 | mww | -4.9521 | 94.3299 | 24.0 | 0 | 0 | 0 | 0 | 0 | 0 | southwest of Sumatra, Indonesia |
| us10004t7g | 2016-02-27T21:29:43.570Z | 6.1 | mww | -51.7897 | 139.5956 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | western Indian-Antarctic Ridge |
| us200050wc | 2016-02-17T17:26:02.210Z | 6.0 | mww | 0.8597 | 129.0605 | 9.0 | 0 | 0 | 0 | 0 | 0 | 0 | 151 km SE of Tobelo, Indonesia |
| us20004zp9 | 2016-02-12T10:02:24.050Z | 6.3 | mww | -9.6338 | 119.4013 | 28.0 | 0 | 0 | 0 | 0 | 0 | 0 | 94 km W of Waingapu, Indonesia |
| us20004yr0 | 2016-02-08T16:19:12.780Z | 6.4 | mww | -6.6207 | 154.7421 | 29.0 | 0 | 0 | 0 | 0 | 0 | 0 | 88 km WSW of Panguna, Papua New Guinea |
| us20004uks | 2016-01-26T03:10:20.750Z | 6.1 | mww | -5.2952 | 153.2454 | 26.0 | 0 | 1 | 0 | 0 | 0 | 0 | 151 km SE of Kokopo, Papua New Guinea |
| us10004dj5 | 2016-01-11T16:38:05.900Z | 6.5 | mww | 3.8965 | 126.8621 | 13.0 | 0 | 0 | 0 | 0 | 0 | 0 | 227 km SE of Sarangani, Philippines |
| us10004ant | 2016-01-01T02:00:39.950Z | 6.3 | mww | -50.5575 | 139.4489 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | western Indian-Antarctic Ridge |
| us100048hc | 2015-12-20T18:47:36.610Z | 6.1 | mww | 3.6455 | 117.6359 | 14.0 | 0 | 0 | 0 | 0 | 0 | 0 | 37 km N of Tarakan, Indonesia |
| us1000489i | 2015-12-19T02:10:53.360Z | 6.0 | mww | -18.3819 | 169.3857 | 10.0 | 0 | 5 | 1 | 1 | 0 | 2 | 128 km N of Isangel, Vanuatu |
| us20004fuz | 2015-12-09T12:58:01.780Z | 6.1 | mww | -16.7374 | 175.2475 | 10.0 | 0 | 4 | 1 | 1 | 0 | 2 | 253 km WNW of Lautoka, Fiji |
| us20004ft7 | 2015-12-09T10:21:48.530Z | 6.9 | mww | -4.1064 | 129.5079 | 21.0 | 0 | 1 | 0 | 0 | 0 | 0 | 107 km SE of Amahai, Indonesia |
| us1000402t | 2015-11-21T09:06:13.460Z | 6.1 | mww | -7.1484 | 129.9375 | 82.0 | 0 | 0 | 0 | 0 | 0 | 0 | Kepulauan Babar, Indonesia |
| us10003zcp | 2015-11-18T18:31:04.570Z | 6.8 | mww | -8.8994 | 158.4217 | 12.6 | 0 | 1 | 1 | 1 | 0 | 2 | 153 km WSW of Buala, Solomon Islands |
| us200041ty | 2015-11-04T03:44:15.190Z | 6.5 | mww | -8.3381 | 124.8754 | 20.0 | 0 | 1 | 0 | 0 | 0 | 0 | 47 km NW of Maubara, Timor Leste |
| us10003q0q | 2015-10-20T21:52:02.560Z | 7.1 | mww | -14.8595 | 167.3028 | 135.0 | 0 | 0 | 0 | 0 | 0 | 0 | 31 km NE of Port-Olry, Vanuatu |
| us20003nqr | 2015-09-24T15:53:27.740Z | 6.6 | mww | -0.6212 | 131.2622 | 18.0 | 0 | 0 | 0 | 0 | 0 | 0 | 28 km N of Sorong, Indonesia |
| us20003jyz | 2015-09-16T14:03:22.110Z | 6.1 | mww | -6.0114 | 151.4768 | 6.0 | 0 | 1 | 0 | 0 | 0 | 0 | 156 km ESE of Kimbe, Papua New Guinea |
| us20003jwc | 2015-09-16T07:40:58.690Z | 6.3 | mww | 1.8841 | 126.4288 | 41.5 | 0 | 0 | 0 | 0 | 0 | 0 | 161 km NW of Ternate, Indonesia |
| us20003h2i | 2015-09-07T08:46:09.050Z | 6.0 | mww | -24.2427 | 179.1278 | 535.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| us100032k6 | 2015-08-15T07:47:06.500Z | 6.4 | mww | -10.8968 | 163.8226 | 8.0 | 0 | 0 | 0 | 0 | 0 | 0 | 213 km ESE of Kirakira, Solomon Islands |
| us100031me | 2015-08-12T18:49:24.080Z | 6.5 | mww | -9.3293 | 157.8772 | 6.4 | 0 | 1 | 1 | 1 | 0 | 2 | 177 km SE of Gizo, Solomon Islands |
| us100030pg | 2015-08-10T04:12:15.810Z | 6.6 | mww | -9.3438 | 158.0525 | 22.0 | 0 | 1 | 1 | 1 | 0 | 2 | 186 km WNW of Malango, Solomon Islands |
| us200030kn | 2015-07-27T21:41:21.710Z | 7.0 | mww | -2.6286 | 138.5277 | 48.0 | 0 | 0 | 0 | 0 | 0 | 0 | 234 km W of Abepura, Indonesia |
| us20002yaw | 2015-07-18T02:27:33.820Z | 7.0 | mww | -10.4012 | 165.1409 | 11.0 | 0 | 0 | 0 | 0 | 0 | 0 | 80 km WNW of Lata, Solomon Islands |
| us20002whh | 2015-07-10T04:12:42.540Z | 6.7 | mww | -9.3070 | 158.4030 | 12.0 | 0 | 1 | 1 | 1 | 0 | 2 | 150 km WNW of Malango, Solomon Islands |
| us10002mw0 | 2015-07-01T19:35:21.460Z | 6.0 | mww | -10.9911 | 162.5558 | 12.0 | 0 | 0 | 0 | 0 | 0 | 0 | 91 km SE of Kirakira, Solomon Islands |
| us10002mhg | 2015-06-30T03:39:29.410Z | 6.0 | mww | -5.4513 | 151.5457 | 43.0 | 0 | 1 | 0 | 0 | 0 | 0 | 146 km SSW of Kokopo, Papua New Guinea |
| us10002bpw | 2015-05-22T23:59:33.770Z | 6.8 | mww | -11.1093 | 163.2154 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 159 km ESE of Kirakira, Solomon Islands |
| us10002bnk | 2015-05-22T21:45:19.480Z | 6.9 | mww | -11.0559 | 163.6959 | 11.2 | 0 | 0 | 0 | 0 | 0 | 0 | 205 km ESE of Kirakira, Solomon Islands |
| us10002b03 | 2015-05-20T22:48:53.420Z | 6.8 | mww | -10.8759 | 164.1694 | 11.0 | 0 | 0 | 0 | 0 | 0 | 0 | 178 km W of Lata, Solomon Islands |
| us100029k5 | 2015-05-15T20:26:56.870Z | 6.0 | mww | -2.5420 | 102.2191 | 151.0 | 0 | 1 | 0 | 0 | 0 | 0 | 106 km ESE of Sungai Penuh, Indonesia |
| us20002das | 2015-05-07T07:10:19.590Z | 7.1 | mww | -7.2175 | 154.5567 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 143 km SW of Panguna, Papua New Guinea |
| us20002bnf | 2015-05-05T01:44:06.380Z | 7.5 | mww | -5.4624 | 151.8751 | 55.0 | 0 | 1 | 0 | 0 | 0 | 0 | 131 km SSW of Kokopo, Papua New Guinea |
| us20002b1r | 2015-05-03T22:32:39.010Z | 6.0 | mww | -5.6314 | 151.6757 | 24.0 | 0 | 1 | 0 | 0 | 0 | 0 | 156 km SSW of Kokopo, Papua New Guinea |
| us20002dhx | 2015-05-01T08:06:52.250Z | 6.0 | mb | -5.4912 | 151.8715 | 35.0 | 0 | 1 | 0 | 0 | 0 | 0 | 134 km SSW of Kokopo, Papua New Guinea |
| us20002am6 | 2015-05-01T08:06:03.480Z | 6.8 | mww | -5.2005 | 151.7773 | 44.0 | 0 | 1 | 0 | 0 | 0 | 0 | 109 km SSW of Kokopo, Papua New Guinea |
| us20002ag9 | 2015-04-30T10:45:02.930Z | 6.7 | mww | -5.3750 | 151.7706 | 31.0 | 0 | 1 | 0 | 0 | 0 | 0 | 126 km SSW of Kokopo, Papua New Guinea |
| us200028qc | 2015-04-24T03:36:42.400Z | 6.1 | mww | -42.0602 | 173.0066 | 48.0 | 0 | 50 | 0 | 0 | 0 | 0 | 73 km S of Wakefield, New Zealand |
| us200028gt | 2015-04-22T22:57:15.650Z | 6.2 | mww | -12.0390 | 166.4320 | 72.0 | 0 | 0 | 0 | 0 | 0 | 0 | 161 km SSE of Lata, Solomon Islands |
| us10001sbf | 2015-03-31T12:18:24.200Z | 6.0 | mww | -4.8946 | 152.4900 | 39.0 | 0 | 1 | 0 | 0 | 0 | 0 | 65 km SSE of Kokopo, Papua New Guinea |
| us10001rvu | 2015-03-29T23:48:31.010Z | 7.5 | mww | -4.7294 | 152.5623 | 41.0 | 0 | 1 | 0 | 0 | 0 | 0 | 53 km SE of Kokopo, Papua New Guinea |
| us10001nab | 2015-03-17T22:12:28.940Z | 6.2 | mww | 1.6686 | 126.5217 | 44.0 | 0 | 0 | 0 | 0 | 0 | 0 | 136 km NW of Ternate, Indonesia |
| us10001mm0 | 2015-03-15T23:17:16.910Z | 6.1 | mww | -0.5409 | 122.3067 | 31.0 | 0 | 0 | 0 | 0 | 0 | 0 | 70 km NW of Luwuk, Indonesia |
| usc000tumx | 2015-03-03T10:37:30.050Z | 6.1 | mww | -0.7789 | 98.7161 | 28.0 | 0 | 1 | 0 | 0 | 0 | 0 | 157 km W of Pariaman, Indonesia |
| usc000ttkd | 2015-02-27T13:45:05.370Z | 7.0 | mww | -7.2968 | 122.5348 | 552.1 | 0 | 1 | 0 | 0 | 0 | 0 | 150 km NNE of Maumere, Indonesia |
| usc000trf9 | 2015-02-19T13:18:32.810Z | 6.4 | mww | -16.4311 | 168.1483 | 10.0 | 0 | 5 | 1 | 1 | 0 | 2 | Vanuatu |
| usb000tq9f | 2015-02-18T09:32:26.770Z | 6.1 | mww | -10.7598 | 164.1216 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 183 km W of Lata, Solomon Islands |
| usc000tker | 2015-01-30T17:57:56.440Z | 6.0 | mww | -21.2452 | 170.1580 | 7.1 | 0 | 0 | 0 | 0 | 0 | 0 | 209 km SSE of Isangel, Vanuatu |
| usc000tihy | 2015-01-23T03:47:27.050Z | 6.8 | mww | -17.0309 | 168.5200 | 220.0 | 0 | 5 | 1 | 1 | 0 | 2 | 81 km NNE of Port-Vila, Vanuatu |
| usc000t8vq | 2014-12-21T11:34:13.570Z | 6.3 | mww | 2.0892 | 126.6483 | 41.0 | 0 | 0 | 0 | 0 | 0 | 0 | 156 km WNW of Tobelo, Indonesia |
| usc000t4cz | 2014-12-07T01:22:02.180Z | 6.6 | mww | -6.5108 | 154.4603 | 23.0 | 0 | 0 | 0 | 0 | 0 | 0 | 115 km W of Panguna, Papua New Guinea |
| usc000t4bd | 2014-12-06T22:05:10.730Z | 6.0 | mww | -6.1100 | 130.4829 | 116.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| usb000t08w | 2014-11-26T14:33:43.640Z | 6.8 | mww | 1.9604 | 126.5751 | 39.0 | 0 | 0 | 0 | 0 | 0 | 0 | 157 km NW of Ternate, Indonesia |
| usb000syhz | 2014-11-21T10:10:19.630Z | 6.5 | mww | 2.2999 | 127.0562 | 35.0 | 0 | 0 | 0 | 0 | 0 | 0 | 123 km WNW of Tobelo, Indonesia |
| usc000sxye | 2014-11-16T22:33:20.450Z | 6.7 | mww | -37.6478 | 179.6621 | 22.0 | 0 | 41 | 0 | 0 | 0 | 0 | 183 km NE of Gisborne, New Zealand |
| usc000sxh8 | 2014-11-15T02:31:41.720Z | 7.1 | mww | 1.8929 | 126.5217 | 45.0 | 0 | 0 | 0 | 0 | 0 | 0 | 155 km NW of Ternate, Indonesia |
| usc000swwj | 2014-11-13T10:24:18.270Z | 6.0 | mww | -15.2155 | 173.0845 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | Fiji region |
| usc000sv94 | 2014-11-07T03:33:55.280Z | 6.6 | mww | -5.9873 | 148.2315 | 53.2 | 0 | 1 | 0 | 0 | 0 | 0 | 76 km NE of Finschhafen, Papua New Guinea |
| usb000shl2 | 2014-10-01T03:38:51.760Z | 6.0 | mww | -6.0706 | 149.5329 | 42.0 | 0 | 1 | 0 | 0 | 0 | 0 | 15 km N of Kandrian, Papua New Guinea |
| usb000sftz | 2014-09-25T09:13:50.000Z | 6.1 | mww | -9.4618 | 156.4122 | 4.0 | 0 | 0 | 0 | 0 | 0 | 0 | 157 km SSW of Gizo, Solomon Islands |
| usb000say6 | 2014-09-10T02:46:06.430Z | 6.2 | mww | -0.2422 | 125.1040 | 35.0 | 0 | 0 | 0 | 0 | 0 | 0 | 172 km S of Tondano, Indonesia |
| usb000s0r6 | 2014-08-06T11:45:22.680Z | 6.2 | mww | -7.2741 | 128.0364 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 179 km NE of Lospalos, Timor Leste |
| usb000rzki | 2014-08-03T00:22:03.680Z | 6.9 | mww | 0.8295 | 146.1688 | 13.0 | 0 | 0 | 0 | 0 | 0 | 0 | Federated States of Micronesia region |
| usb000ry9u | 2014-07-29T13:27:40.080Z | 6.0 | mww | -3.4220 | 146.7690 | 9.8 | 0 | 1 | 0 | 0 | 0 | 0 | 163 km SSW of Lorengau, Papua New Guinea |
| usc000rrmg | 2014-07-08T12:56:25.920Z | 6.2 | mww | -17.6864 | 168.3982 | 110.2 | 0 | 5 | 1 | 1 | 0 | 2 | 10 km ENE of Port-Vila, Vanuatu |
| usc000rqs7 | 2014-07-05T09:39:27.790Z | 6.0 | mww | 1.9335 | 96.9388 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | 86 km SE of Sinabang, Indonesia |
| usc000rqgz | 2014-07-04T15:00:27.860Z | 6.5 | mww | -6.2304 | 152.8075 | 20.0 | 0 | 1 | 0 | 0 | 0 | 0 | 217 km SSE of Kokopo, Papua New Guinea |
| usb000rgsn | 2014-06-19T10:17:55.520Z | 6.2 | mww | -13.5585 | 166.8278 | 36.0 | 0 | 0 | 0 | 0 | 0 | 0 | 85 km WNW of Sola, Vanuatu |
| usc000rfh2 | 2014-06-14T11:10:59.850Z | 6.5 | mww | -10.1229 | 91.0921 | 4.0 | 0 | 0 | 0 | 0 | 0 | 0 | South Indian Ocean |
| usb000qt4l | 2014-05-18T01:02:32.610Z | 6.0 | mww | 4.2485 | 92.7574 | 35.0 | 0 | 0 | 0 | 0 | 0 | 0 | off the west coast of northern Sumatra |
| usb000qcqe | 2014-05-07T04:20:33.870Z | 6.0 | mww | -6.9599 | 154.9011 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 96 km SW of Panguna, Papua New Guinea |
| usb000q98e | 2014-05-04T09:25:15.960Z | 6.3 | mww | -25.8072 | 178.2401 | 634.2 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| usb000q98a | 2014-05-04T09:15:52.880Z | 6.6 | mww | -24.6108 | 179.0856 | 527.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| usb000q66s | 2014-05-01T06:36:35.550Z | 6.6 | mww | -21.4542 | 170.3546 | 106.0 | 0 | 0 | 0 | 0 | 0 | 0 | 239 km SSE of Isangel, Vanuatu |
| usb000prqv | 2014-04-20T00:15:58.100Z | 6.2 | mww | -7.1646 | 155.3351 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | 95 km S of Panguna, Papua New Guinea |
| usb000pr89 | 2014-04-19T13:28:00.810Z | 7.5 | mww | -6.7547 | 155.0241 | 43.4 | 0 | 0 | 0 | 0 | 0 | 0 | 70 km SW of Panguna, Papua New Guinea |
| usb000pqwe | 2014-04-19T01:04:03.820Z | 6.6 | mww | -6.6558 | 155.0869 | 29.0 | 0 | 0 | 0 | 0 | 0 | 0 | 57 km SW of Panguna, Papua New Guinea |
| usb000pptc | 2014-04-18T04:13:12.040Z | 6.1 | mww | -11.1387 | 164.8139 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 116 km WSW of Lata, Solomon Islands |
| usc000pish | 2014-04-13T13:24:59.710Z | 6.6 | mww | -11.1284 | 162.0520 | 10.0 | 0 | 1 | 1 | 1 | 0 | 2 | 75 km S of Kirakira, Solomon Islands |
| usc000piqj | 2014-04-13T12:36:19.230Z | 7.4 | mww | -11.4633 | 162.0511 | 39.0 | 0 | 0 | 0 | 0 | 0 | 0 | 112 km S of Kirakira, Solomon Islands |
| usc000phx5 | 2014-04-12T20:14:39.300Z | 7.6 | mww | -11.2701 | 162.1481 | 22.6 | 0 | 0 | 0 | 0 | 0 | 0 | 93 km SSE of Kirakira, Solomon Islands |
| usc000phaj | 2014-04-12T05:24:23.270Z | 6.1 | mww | -7.1033 | 155.2380 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | 91 km SSW of Panguna, Papua New Guinea |
| usc000pfuy | 2014-04-11T08:16:45.660Z | 6.5 | mww | -6.7878 | 154.9502 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | 78 km SW of Panguna, Papua New Guinea |
| usc000pft9 | 2014-04-11T07:07:23.130Z | 7.1 | mww | -6.5858 | 155.0485 | 60.5 | 0 | 0 | 0 | 0 | 0 | 0 | 56 km WSW of Panguna, Papua New Guinea |
| usc000p4ty | 2014-04-04T11:40:32.000Z | 6.0 | mww | -10.5365 | 161.7027 | 57.0 | 0 | 1 | 0 | 0 | 0 | 0 | 25 km WSW of Kirakira, Solomon Islands |
| usc000nsgk | 2014-03-27T03:49:42.710Z | 6.0 | mww | -12.0989 | 166.5894 | 98.0 | 0 | 0 | 0 | 0 | 0 | 0 | 174 km SSE of Lata, Solomon Islands |
| usc000nqnq | 2014-03-26T03:29:35.720Z | 6.3 | mww | -26.1692 | 179.2877 | 495.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| usc000n8ez | 2014-03-11T22:03:09.810Z | 6.1 | mww | -3.0856 | 148.5531 | 7.0 | 0 | 1 | 1 | 1 | 0 | 2 | 183 km SE of Lorengau, Papua New Guinea |
| usb000n1ex | 2014-03-05T09:56:57.840Z | 6.3 | mww | -14.7378 | 169.8234 | 638.0 | 0 | 0 | 0 | 0 | 0 | 0 | 262 km ESE of Sola, Vanuatu |
| usc000mlk4 | 2014-02-09T14:56:39.110Z | 6.0 | mww | -5.9651 | 154.4350 | 41.8 | 0 | 0 | 0 | 0 | 0 | 0 | 122 km WNW of Panguna, Papua New Guinea |
| usc000mjye | 2014-02-07T08:40:13.550Z | 6.5 | mww | -15.0691 | 167.3721 | 122.0 | 0 | 0 | 0 | 0 | 0 | 0 | 32 km E of Port-Olry, Vanuatu |
| usb000m7wd | 2014-01-25T05:14:18.510Z | 6.1 | mww | -7.9855 | 109.2653 | 66.0 | 0 | 1 | 0 | 0 | 0 | 0 | 39 km S of Kroya, Indonesia |
| usb000m4i4 | 2014-01-20T02:52:44.350Z | 6.1 | mww | -40.6595 | 175.8144 | 28.0 | 0 | 114 | 0 | 0 | 0 | 0 | 35 km NNE of Masterton, New Zealand |
| usc000lvb5 | 2014-01-01T16:03:29.000Z | 6.5 | mww | -13.8633 | 167.2490 | 187.0 | 0 | 0 | 0 | 0 | 0 | 0 | 32 km W of Sola, Vanuatu |
| usb000l8pb | 2013-12-01T06:29:57.800Z | 6.0 | mww | 2.0440 | 96.8261 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | 69 km SE of Sinabang, Indonesia |
| usb000l8mb | 2013-12-01T01:24:13.520Z | 6.4 | mww | -7.0269 | 128.3791 | 9.9 | 0 | 0 | 0 | 0 | 0 | 0 | 224 km NE of Lospalos, Timor Leste |
| usb000l219 | 2013-11-19T13:32:51.230Z | 6.0 | mww | 2.6403 | 128.4339 | 38.0 | 0 | 0 | 0 | 0 | 0 | 0 | 111 km NNE of Tobelo, Indonesia |
| usb000kemb | 2013-10-16T10:30:58.550Z | 6.8 | mww | -6.4456 | 154.9310 | 35.0 | 0 | 0 | 0 | 0 | 0 | 0 | 62 km WSW of Panguna, Papua New Guinea |
| usb000jx0m | 2013-09-21T01:39:15.570Z | 6.1 | mww | -7.3308 | 120.0106 | 549.9 | 0 | 2 | 0 | 0 | 0 | 0 | 129 km N of Labuan Bajo, Indonesia |
| usb000jelf | 2013-09-01T11:52:29.930Z | 6.5 | mww | -7.4400 | 128.2209 | 112.0 | 0 | 0 | 0 | 0 | 0 | 0 | 180 km NE of Lospalos, Timor Leste |
| usb000jcfu | 2013-08-28T02:54:41.290Z | 6.2 | mww | -27.7829 | 179.6335 | 478.0 | 0 | 1 | 0 | 0 | 0 | 0 | Kermadec Islands region |
| usb000j4iz | 2013-08-16T02:31:05.750Z | 6.5 | mww | -41.7340 | 174.1520 | 8.2 | 0 | 69 | 0 | 0 | 0 | 0 | 29 km SE of Blenheim, New Zealand |
| usb000j0vl | 2013-08-12T00:53:43.980Z | 6.0 | mww | -7.1354 | 129.8088 | 95.0 | 0 | 0 | 0 | 0 | 0 | 0 | Kepulauan Babar, Indonesia |
| usc000ipje | 2013-07-26T07:07:15.630Z | 6.1 | mww | -15.3790 | 167.6890 | 124.0 | 0 | 5 | 0 | 0 | 0 | 0 | 58 km ENE of Luganville, Vanuatu |
| usb000iivv | 2013-07-21T05:09:31.450Z | 6.5 | mww | -41.7040 | 174.3370 | 17.0 | 0 | 70 | 0 | 0 | 0 | 0 | 38 km ESE of Blenheim, New Zealand |
| usb000i8ey | 2013-07-07T20:30:06.850Z | 6.6 | mww | -6.0290 | 149.7060 | 56.0 | 0 | 0 | 0 | 0 | 0 | 0 | 26 km NE of Kandrian, Papua New Guinea |
| usb000i89z | 2013-07-07T18:35:30.740Z | 7.3 | mww | -3.9170 | 153.9270 | 385.5 | 0 | 0 | 0 | 0 | 0 | 0 | 190 km ENE of Kokopo, Papua New Guinea |
| usb000i7na | 2013-07-06T05:05:06.650Z | 6.0 | mww | -3.2690 | 100.5640 | 21.0 | 0 | 1 | 0 | 0 | 0 | 0 | 162 km SW of Sungai Penuh, Indonesia |
| usb000i6rh | 2013-07-04T17:15:54.540Z | 6.1 | mww | -7.0280 | 155.7260 | 29.0 | 0 | 0 | 0 | 0 | 0 | 0 | 83 km SSE of Panguna, Papua New Guinea |
| usb000i4re | 2013-07-02T07:37:02.610Z | 6.1 | mww | 4.6450 | 96.6650 | 13.0 | 0 | 0 | 0 | 0 | 0 | 0 | 61 km S of Bireun, Indonesia |
| usc000hrgh | 2013-06-15T11:20:36.020Z | 6.0 | mww | -33.8530 | 179.4020 | 195.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Kermadec Islands |
| usc000hpsd | 2013-06-13T16:47:23.320Z | 6.7 | mww | -10.0040 | 107.2360 | 9.0 | 0 | 1 | 1 | 1 | 0 | 2 | south of Java, Indonesia |
| usb000hdx2 | 2013-06-05T04:47:26.240Z | 6.1 | mww | -11.4010 | 166.2990 | 39.0 | 0 | 0 | 0 | 0 | 0 | 0 | 92 km SE of Lata, Solomon Islands |
| usc000gpwn | 2013-05-07T10:10:48.700Z | 6.0 | mww | -19.6220 | 175.0510 | 11.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| usb000gen8 | 2013-04-23T23:14:40.630Z | 6.5 | mww | -3.8980 | 152.1270 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 33 km N of Rabaul, Papua New Guinea |
| usb000g8my | 2013-04-16T22:55:26.680Z | 6.6 | mww | -3.2140 | 142.5420 | 13.0 | 0 | 0 | 0 | 0 | 0 | 0 | 23 km ESE of Aitape, Papua New Guinea |
| usb000g6lc | 2013-04-14T01:32:22.640Z | 6.6 | mww | -6.4750 | 154.6070 | 31.0 | 0 | 0 | 0 | 0 | 0 | 0 | 98 km W of Panguna, Papua New Guinea |
| usb000g6it | 2013-04-13T22:49:50.550Z | 6.0 | mww | -19.1410 | 169.5350 | 280.2 | 0 | 5 | 1 | 1 | 0 | 2 | 51 km NNE of Isangel, Vanuatu |
| usb000g13s | 2013-04-06T04:42:35.860Z | 7.0 | mww | -3.5170 | 138.4760 | 66.0 | 0 | 0 | 0 | 0 | 0 | 0 | 260 km WSW of Abepura, Indonesia |
| usb000frwy | 2013-03-24T08:13:45.130Z | 6.1 | mww | -20.7570 | 173.3700 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | Vanuatu region |
| usb000fij4 | 2013-03-10T22:51:50.800Z | 6.5 | mww | -6.5980 | 148.1740 | 28.0 | 0 | 1 | 0 | 0 | 0 | 0 | 36 km E of Finschhafen, Papua New Guinea |
| usc000f4zf | 2013-02-10T18:39:32.140Z | 6.0 | mww | -10.9400 | 165.4610 | 11.0 | 0 | 0 | 0 | 0 | 0 | 0 | 43 km WSW of Lata, Solomon Islands |
| usc000f4n5 | 2013-02-09T21:02:22.790Z | 6.6 | mww | -10.9940 | 165.7410 | 18.0 | 0 | 0 | 0 | 0 | 0 | 0 | 30 km SSW of Lata, Solomon Islands |
| usc000f40j | 2013-02-08T15:26:38.470Z | 7.1 | mww | -10.9280 | 166.0180 | 21.0 | 0 | 0 | 0 | 0 | 0 | 0 | 32 km SE of Lata, Solomon Islands |
| usc000f3x8 | 2013-02-08T11:12:11.510Z | 6.8 | mww | -10.8380 | 165.9690 | 12.0 | 0 | 0 | 0 | 0 | 0 | 0 | 22 km ESE of Lata, Solomon Islands |
| usc000f3fx | 2013-02-07T18:59:16.270Z | 6.7 | mww | -10.9970 | 165.6550 | 11.0 | 0 | 0 | 0 | 0 | 0 | 0 | 33 km SSW of Lata, Solomon Islands |
| usc000f2ul | 2013-02-07T00:30:10.790Z | 6.0 | mww | -11.6580 | 164.9400 | 8.0 | 0 | 0 | 0 | 0 | 0 | 0 | 139 km SW of Lata, Solomon Islands |
| usc000f2ap | 2013-02-06T11:53:55.190Z | 6.0 | mww | -11.2430 | 165.7280 | 14.0 | 0 | 0 | 0 | 0 | 0 | 0 | 57 km S of Lata, Solomon Islands |
| usc000f29g | 2013-02-06T10:33:17.460Z | 6.0 | mwb | -10.6420 | 164.7650 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 113 km W of Lata, Solomon Islands |
| usc000f23y | 2013-02-06T06:35:19.250Z | 6.1 | mwc | -10.7910 | 164.5510 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 136 km W of Lata, Solomon Islands |
| usc000f1ts | 2013-02-06T01:54:14.610Z | 7.0 | mww | -10.4990 | 165.5880 | 8.8 | 0 | 0 | 0 | 0 | 0 | 0 | 33 km NW of Lata, Solomon Islands |
| usc000f1se | 2013-02-06T01:23:19.760Z | 7.1 | mww | -11.1830 | 164.8820 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 112 km WSW of Lata, Solomon Islands |
| usc000f1s0 | 2013-02-06T01:12:25.830Z | 8.0 | mww | -10.7990 | 165.1140 | 24.0 | 0 | 0 | 0 | 0 | 0 | 0 | 2013 Santa Cruz Islands Earthquake |
| usc000f1r5 | 2013-02-06T00:07:22.100Z | 6.0 | mww | -10.8640 | 165.2480 | 11.0 | 0 | 0 | 0 | 0 | 0 | 0 | 62 km WSW of Lata, Solomon Islands |
| usc000f05y | 2013-02-02T18:58:06.480Z | 6.0 | mwb | -10.8870 | 165.2840 | 6.0 | 0 | 0 | 0 | 0 | 0 | 0 | 58 km WSW of Lata, Solomon Islands |
| usc000ezw4 | 2013-02-01T22:18:33.070Z | 6.4 | mww | -11.1200 | 165.3780 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 63 km SW of Lata, Solomon Islands |
| usc000ezv6 | 2013-02-01T22:16:34.170Z | 6.3 | mww | -10.8960 | 165.3790 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 49 km WSW of Lata, Solomon Islands |
| usc000ezil | 2013-02-01T05:36:41.790Z | 6.0 | mww | -11.1040 | 165.5320 | 15.0 | 0 | 0 | 0 | 0 | 0 | 0 | 50 km SW of Lata, Solomon Islands |
| usc000ez0w | 2013-01-31T03:33:43.720Z | 6.1 | mww | -10.6400 | 166.3670 | 9.0 | 0 | 0 | 0 | 0 | 0 | 0 | 63 km E of Lata, Solomon Islands |
| usc000eyur | 2013-01-30T23:03:43.660Z | 6.1 | mww | -10.6340 | 166.3720 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 63 km E of Lata, Solomon Islands |
| usb000esgn | 2013-01-21T22:22:52.760Z | 6.1 | mww | 4.9270 | 95.9070 | 12.0 | 0 | 0 | 0 | 0 | 0 | 0 | 50 km S of Sigli, Indonesia |
| usp000jx85 | 2012-12-21T22:28:08.570Z | 6.7 | mww | -14.3440 | 167.2860 | 200.7 | 0 | 0 | 0 | 0 | 0 | 0 | 59 km SSW of Sola, Vanuatu |
| usp000jx2e | 2012-12-17T09:16:30.900Z | 6.1 | mww | -0.6490 | 123.8070 | 44.2 | 0 | 0 | 0 | 0 | 0 | 0 | 118 km ENE of Luwuk, Indonesia |
| usp000jx05 | 2012-12-15T19:30:02.170Z | 6.1 | mww | -4.6320 | 153.0160 | 52.0 | 0 | 0 | 0 | 0 | 0 | 0 | 88 km ESE of Kokopo, Papua New Guinea |
| usp000jwu3 | 2012-12-11T06:18:27.330Z | 6.0 | mww | 0.5330 | 126.2310 | 30.0 | 0 | 0 | 0 | 0 | 0 | 0 | Molucca Sea |
| usp000jwt8 | 2012-12-10T16:53:08.770Z | 7.1 | mww | -6.5330 | 129.8250 | 155.0 | 0 | 0 | 0 | 0 | 0 | 0 | Banda Sea |
| usp000jwmk | 2012-12-07T18:19:06.310Z | 6.3 | mww | -38.4280 | 176.0670 | 163.0 | 0 | 119 | 0 | 0 | 0 | 0 | 27 km SE of Tokoroa, New Zealand |
| usp000jwax | 2012-12-02T00:54:22.690Z | 6.1 | mww | -16.9750 | 167.6450 | 32.0 | 0 | 5 | 0 | 0 | 0 | 0 | 99 km SSE of Lakatoro, Vanuatu |
| usp000jvtm | 2012-11-19T09:44:34.120Z | 6.0 | mww | -5.7050 | 151.6020 | 13.0 | 0 | 0 | 0 | 0 | 0 | 0 | 163 km E of Kimbe, Papua New Guinea |
| usp000ju7q | 2012-10-20T23:00:32.450Z | 6.2 | mww | -13.5520 | 166.5640 | 36.0 | 0 | 0 | 0 | 0 | 0 | 0 | 112 km WNW of Sola, Vanuatu |
| usp000ju30 | 2012-10-17T04:42:30.400Z | 6.0 | mww | 4.2320 | 124.5200 | 326.0 | 0 | 1 | 0 | 0 | 0 | 0 | 166 km SW of Sarangani, Philippines |
| usp000jtvw | 2012-10-12T00:31:28.270Z | 6.6 | mww | -4.8920 | 134.0300 | 13.0 | 0 | 0 | 0 | 0 | 0 | 0 | 163 km ENE of Tual, Indonesia |
| usp000jtqw | 2012-10-08T11:43:31.420Z | 6.1 | mww | -4.4720 | 129.1290 | 10.0 | 0 | 1 | 0 | 0 | 0 | 0 | 127 km S of Amahai, Indonesia |
| usp000jsa4 | 2012-09-14T04:51:47.070Z | 6.2 | mww | -3.3190 | 100.5940 | 19.0 | 0 | 1 | 0 | 0 | 0 | 0 | 165 km SSW of Sungai Penuh, Indonesia |
| usp000jrzt | 2012-09-08T10:51:44.200Z | 6.1 | mww | -3.1770 | 135.1090 | 21.0 | 0 | 0 | 0 | 0 | 0 | 0 | 48 km WNW of Nabire, Indonesia |
| usp000jrsq | 2012-09-05T13:09:10.060Z | 6.0 | mww | -12.4760 | 166.5130 | 27.0 | 0 | 0 | 0 | 0 | 0 | 0 | 191 km NW of Sola, Vanuatu |
| usp000jrkr | 2012-09-03T18:23:05.230Z | 6.1 | mww | -10.7080 | 113.9310 | 14.0 | 0 | 0 | 0 | 0 | 0 | 0 | 251 km SSW of Jimbaran, Indonesia |
| usp000jqrz | 2012-08-26T15:05:37.080Z | 6.6 | mww | 2.1900 | 126.8370 | 91.1 | 0 | 0 | 0 | 0 | 0 | 0 | 140 km WNW of Tobelo, Indonesia |
| usp000jqha | 2012-08-19T22:41:49.810Z | 6.2 | mww | -4.7660 | 144.5700 | 73.0 | 0 | 0 | 0 | 0 | 0 | 0 | 95 km SE of Angoram, Papua New Guinea |
| usp000jqf3 | 2012-08-18T09:41:52.450Z | 6.3 | mww | -1.3150 | 120.0960 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 51 km SSE of Palu, Indonesia |
| usp000jpsa | 2012-08-02T09:56:41.740Z | 6.1 | mww | -4.6540 | 153.2750 | 46.0 | 0 | 0 | 0 | 0 | 0 | 0 | 116 km ESE of Kokopo, Papua New Guinea |
| usp000jpjk | 2012-07-28T20:03:56.800Z | 6.5 | mww | -4.6510 | 153.1730 | 41.0 | 0 | 0 | 0 | 0 | 0 | 0 | 105 km ESE of Kokopo, Papua New Guinea |
| usp000jpeh | 2012-07-25T11:20:27.030Z | 6.4 | mww | -9.6940 | 159.7270 | 20.0 | 0 | 1 | 1 | 1 | 0 | 2 | 1 km E of Malango, Solomon Islands |
| usp000jpe1 | 2012-07-25T00:27:45.260Z | 6.4 | mww | 2.7070 | 96.0450 | 22.0 | 0 | 0 | 0 | 0 | 0 | 0 | 44 km NW of Sinabang, Indonesia |
| usp000jnnv | 2012-07-06T02:28:22.190Z | 6.3 | mww | -14.6570 | 167.3400 | 160.1 | 0 | 0 | 0 | 0 | 0 | 0 | 51 km NE of Port-Olry, Vanuatu |
| usp000jnj4 | 2012-07-03T10:36:15.520Z | 6.3 | mww | -40.0230 | 173.7560 | 229.8 | 0 | 93 | 0 | 0 | 0 | 0 | 63 km S of Opunake, New Zealand |
| usp000jn41 | 2012-06-23T04:34:53.180Z | 6.1 | mww | 3.0090 | 97.8960 | 95.0 | 0 | 0 | 0 | 0 | 0 | 0 | 66 km W of Kabanjahe, Indonesia |
| usp000jkuj | 2012-05-23T22:59:52.700Z | 6.0 | mww | -50.4200 | 139.5160 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | western Indian-Antarctic Ridge |
| usp000jjat | 2012-04-21T01:25:13.200Z | 6.0 | mwc | -1.6350 | 134.1970 | 17.4 | 0 | 0 | 0 | 0 | 0 | 0 | 86 km S of Manokwari, Indonesia |
| usp000jjaq | 2012-04-21T01:16:52.740Z | 6.7 | mww | -1.6170 | 134.2760 | 16.0 | 0 | 0 | 0 | 0 | 0 | 0 | 86 km SSE of Manokwari, Indonesia |
| usp000jj41 | 2012-04-17T07:13:49.000Z | 6.8 | mww | -5.4620 | 147.1170 | 198.0 | 0 | 1 | 0 | 0 | 0 | 0 | 140 km N of Lae, Papua New Guinea |
| usp000jj0a | 2012-04-15T05:57:40.060Z | 6.2 | mww | 2.5810 | 90.2690 | 25.0 | 0 | 0 | 0 | 0 | 0 | 0 | off the west coast of northern Sumatra |
| usp000jhzj | 2012-04-14T22:05:26.430Z | 6.2 | mww | -18.9720 | 168.7410 | 11.0 | 0 | 4 | 0 | 0 | 0 | 0 | 84 km NW of Isangel, Vanuatu |
| usp000jhjb | 2012-04-11T10:43:10.850Z | 8.2 | mwc | 0.8020 | 92.4630 | 25.1 | 0 | 0 | 0 | 0 | 0 | 0 | 2012 Wharton Basin Aftershock |
| usp000jhhg | 2012-04-11T09:27:56.760Z | 6.0 | mb | 1.2540 | 91.7350 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | North Indian Ocean |
| official20120411083836720_20 | 2012-04-11T08:38:36.720Z | 8.6 | mw | 2.3270 | 93.0630 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | 2012 Wharton Basin Earthquake |
| usp000jhb2 | 2012-04-06T16:15:58.010Z | 6.1 | mww | -4.5510 | 153.4570 | 108.5 | 0 | 0 | 0 | 0 | 0 | 0 | 133 km E of Kokopo, Papua New Guinea |
| usp000jgm3 | 2012-03-21T22:15:06.130Z | 6.6 | mww | -6.2420 | 145.9550 | 118.0 | 0 | 1 | 0 | 0 | 0 | 0 | 11 km ENE of Kainantu, Papua New Guinea |
| usp000jghh | 2012-03-20T17:56:18.800Z | 6.1 | mww | -3.8120 | 140.2660 | 66.0 | 0 | 0 | 0 | 0 | 0 | 0 | 140 km SSW of Abepura, Indonesia |
| usp000jg91 | 2012-03-14T21:13:08.040Z | 6.2 | mww | -5.5950 | 151.0420 | 28.0 | 0 | 0 | 0 | 0 | 0 | 0 | 100 km E of Kimbe, Papua New Guinea |
| usp000jfzj | 2012-03-09T07:09:50.950Z | 6.7 | mww | -19.1250 | 169.6130 | 16.0 | 0 | 4 | 0 | 0 | 0 | 0 | 57 km NE of Isangel, Vanuatu |
| usp000jfqx | 2012-03-03T12:19:55.090Z | 6.6 | mww | -22.1410 | 170.3400 | 14.0 | 0 | 0 | 0 | 0 | 0 | 0 | 262 km ESE of Tadine, New Caledonia |
| usp000jexf | 2012-02-14T08:19:55.470Z | 6.4 | mww | -10.3900 | 161.1020 | 51.0 | 0 | 1 | 0 | 0 | 0 | 0 | 89 km W of Kirakira, Solomon Islands |
| usp000jehw | 2012-02-05T16:40:39.160Z | 6.1 | mww | -17.9480 | 167.2260 | 8.0 | 0 | 4 | 0 | 0 | 0 | 0 | 117 km WSW of Port-Vila, Vanuatu |
| usp000jegv | 2012-02-05T00:15:38.900Z | 6.1 | mww | -18.8940 | 168.9170 | 145.0 | 0 | 4 | 0 | 0 | 0 | 0 | 81 km NNW of Isangel, Vanuatu |
| usp000jed1 | 2012-02-03T03:46:21.150Z | 6.1 | mww | -17.3780 | 167.2770 | 8.0 | 0 | 4 | 0 | 0 | 0 | 0 | 116 km WNW of Port-Vila, Vanuatu |
| usp000jeag | 2012-02-02T13:34:40.650Z | 7.1 | mww | -17.8270 | 167.1330 | 23.0 | 0 | 4 | 0 | 0 | 0 | 0 | 125 km W of Port-Vila, Vanuatu |
| usp000jdwh | 2012-01-24T00:52:05.230Z | 6.3 | mww | -24.9770 | 178.5200 | 580.3 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| usp000jdar | 2012-01-10T18:36:59.080Z | 7.2 | mww | 2.4330 | 93.2100 | 19.0 | 0 | 0 | 0 | 0 | 0 | 0 | off the west coast of northern Sumatra |
| usp000jd8k | 2012-01-09T04:07:14.670Z | 6.4 | mww | -10.6170 | 165.1600 | 28.0 | 0 | 0 | 0 | 0 | 0 | 0 | 70 km W of Lata, Solomon Islands |
| usp000jc5z | 2011-12-14T05:04:58.630Z | 7.1 | mww | -7.5510 | 146.8090 | 135.0 | 0 | 1 | 0 | 0 | 0 | 0 | 25 km SSE of Wau, Papua New Guinea |
| usp000jc4z | 2011-12-13T07:52:11.930Z | 6.0 | mww | 0.0410 | 123.0300 | 161.0 | 0 | 0 | 0 | 0 | 0 | 0 | 55 km S of Gorontalo, Indonesia |
| usp000jbhn | 2011-11-28T12:26:45.450Z | 6.1 | mww | -5.4800 | 153.7330 | 25.0 | 0 | 0 | 0 | 0 | 0 | 0 | 205 km SE of Kokopo, Papua New Guinea |
| usp000jav0 | 2011-11-14T04:05:11.390Z | 6.3 | mww | -0.9490 | 126.9100 | 17.0 | 0 | 0 | 0 | 0 | 0 | 0 | 199 km SSW of Ternate, Indonesia |
| usp000j9ge | 2011-10-18T05:05:06.250Z | 6.1 | mww | -5.7850 | 151.0370 | 26.0 | 0 | 0 | 0 | 0 | 0 | 0 | 102 km ESE of Kimbe, Papua New Guinea |
| usp000j9as | 2011-10-14T03:35:14.810Z | 6.5 | mww | -6.5700 | 147.8810 | 37.0 | 0 | 1 | 0 | 0 | 0 | 0 | 4 km ESE of Finschhafen, Papua New Guinea |
| usp000j99g | 2011-10-13T03:16:30.160Z | 6.1 | mww | -9.3500 | 114.5870 | 39.0 | 0 | 0 | 0 | 0 | 0 | 0 | 88 km SW of Jimbaran, Indonesia |
| usp000j7nn | 2011-09-05T17:55:11.220Z | 6.7 | mww | 2.9650 | 97.8930 | 91.0 | 0 | 0 | 0 | 0 | 0 | 0 | 68 km WSW of Kabanjahe, Indonesia |
| usp000j7jb | 2011-09-03T22:55:40.920Z | 7.0 | mww | -20.6710 | 169.7160 | 185.1 | 0 | 0 | 0 | 0 | 0 | 0 | 133 km SSE of Isangel, Vanuatu |
| usp000j7bw | 2011-09-01T06:14:38.870Z | 6.0 | mww | -12.3600 | 166.6560 | 41.0 | 0 | 0 | 0 | 0 | 0 | 0 | 193 km NNW of Sola, Vanuatu |
| usp000j78h | 2011-08-30T06:57:41.610Z | 6.9 | mww | -6.3620 | 126.7520 | 469.8 | 0 | 0 | 0 | 0 | 0 | 0 | 236 km N of Baukau, Timor Leste |
| usp000j6zp | 2011-08-24T23:06:17.090Z | 6.2 | mww | -18.1550 | 167.7270 | 13.0 | 0 | 4 | 0 | 0 | 0 | 0 | 77 km SW of Port-Vila, Vanuatu |
| usp000j6vx | 2011-08-22T20:12:20.950Z | 6.1 | mww | -6.2820 | 104.0540 | 29.0 | 0 | 0 | 0 | 0 | 0 | 0 | 163 km SW of Bandar Lampung, Indonesia |
| usp000j6rj | 2011-08-20T18:19:23.550Z | 7.1 | mww | -18.3110 | 168.2180 | 28.0 | 0 | 4 | 0 | 0 | 0 | 0 | 64 km S of Port-Vila, Vanuatu |
| usp000j6rb | 2011-08-20T17:13:06.380Z | 6.5 | mwc | -18.3080 | 168.1560 | 35.0 | 0 | 4 | 0 | 0 | 0 | 0 | 65 km SSW of Port-Vila, Vanuatu |
| usp000j6r4 | 2011-08-20T16:55:02.810Z | 7.2 | mww | -18.3650 | 168.1430 | 32.0 | 0 | 4 | 0 | 0 | 0 | 0 | 71 km SSW of Port-Vila, Vanuatu |
| usp000j6hz | 2011-08-16T11:03:56.430Z | 6.1 | mww | -2.3230 | 128.0110 | 26.0 | 0 | 1 | 0 | 0 | 0 | 0 | 151 km NW of Amahai, Indonesia |
| usp000j5t4 | 2011-07-31T23:38:56.610Z | 6.6 | mww | -3.5180 | 144.8280 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 103 km NE of Angoram, Papua New Guinea |
| usp000j5sk | 2011-07-31T14:34:47.320Z | 6.1 | mww | -17.0160 | 171.5790 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | Vanuatu region |
| usp000j5nv | 2011-07-29T07:42:23.400Z | 6.7 | mww | -23.8010 | 179.7510 | 532.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| usp000j5eq | 2011-07-25T00:50:47.590Z | 6.3 | mww | -3.1820 | 150.6110 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 70 km SSW of Kavieng, Papua New Guinea |
| usp000j57s | 2011-07-20T22:04:59.320Z | 6.0 | mww | -10.3400 | 162.0100 | 21.0 | 0 | 1 | 0 | 0 | 0 | 0 | 16 km NE of Kirakira, Solomon Islands |
| usp000j3sp | 2011-06-26T12:16:38.600Z | 6.3 | mww | -2.3840 | 136.6310 | 17.0 | 0 | 0 | 0 | 0 | 0 | 0 | 146 km SSE of Biak, Indonesia |
| usp000j3n9 | 2011-06-24T06:33:07.850Z | 6.1 | mwc | -10.9250 | 165.9310 | 72.1 | 0 | 0 | 0 | 0 | 0 | 0 | 26 km SSE of Lata, Solomon Islands |
| usp000j3gd | 2011-06-21T02:04:15.940Z | 6.0 | mww | -11.4790 | 165.5510 | 14.0 | 0 | 0 | 0 | 0 | 0 | 0 | 87 km SSW of Lata, Solomon Islands |
| usp000j37m | 2011-06-16T00:03:35.790Z | 6.4 | mww | -5.9280 | 151.0400 | 16.0 | 0 | 0 | 0 | 0 | 0 | 0 | 108 km ESE of Kimbe, Papua New Guinea |
| usp000j348 | 2011-06-13T14:31:22.990Z | 6.3 | mww | 2.5150 | 126.4570 | 61.1 | 0 | 0 | 0 | 0 | 0 | 0 | 193 km WNW of Tobelo, Indonesia |
| usp000j1nf | 2011-05-15T18:37:10.370Z | 6.4 | mww | -6.1040 | 154.4140 | 40.0 | 0 | 0 | 0 | 0 | 0 | 0 | 120 km WNW of Panguna, Papua New Guinea |
| usp000j1a8 | 2011-05-10T08:55:08.930Z | 6.8 | mww | -20.2440 | 168.2260 | 11.0 | 0 | 7 | 0 | 0 | 0 | 0 | 124 km NE of Wé, New Caledonia |
| usp000j0hc | 2011-04-24T23:07:51.490Z | 6.1 | mww | -4.5860 | 122.7710 | 8.0 | 0 | 0 | 0 | 0 | 0 | 0 | 47 km NE of Katabu, Indonesia |
| usp000j0eh | 2011-04-23T04:16:54.720Z | 6.8 | mww | -10.3750 | 161.2000 | 79.0 | 0 | 1 | 0 | 0 | 0 | 0 | 79 km W of Kirakira, Solomon Islands |
| usp000j06q | 2011-04-18T13:03:02.730Z | 6.6 | mww | -34.3360 | 179.8740 | 86.0 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Kermadec Islands |
| usp000hzd7 | 2011-04-06T14:01:42.560Z | 6.0 | mww | 1.6120 | 97.0860 | 20.0 | 0 | 0 | 0 | 0 | 0 | 0 | 108 km SW of Singkil, Indonesia |
| usp000hz7h | 2011-04-03T20:06:40.390Z | 6.7 | mww | -9.8480 | 107.6930 | 14.0 | 0 | 1 | 1 | 1 | 0 | 2 | 278 km SSW of Kawalu, Indonesia |
| usp000hxm2 | 2011-03-17T02:48:00.030Z | 6.2 | mww | -17.2750 | 167.8260 | 17.0 | 0 | 4 | 0 | 0 | 0 | 0 | 72 km NW of Port-Vila, Vanuatu |
| usp000hvn3 | 2011-03-10T17:08:36.860Z | 6.5 | mww | -6.8730 | 116.7200 | 510.6 | 0 | 0 | 0 | 0 | 0 | 0 | 178 km NNE of Gili Air, Indonesia |
| usp000hvkj | 2011-03-09T21:24:49.760Z | 6.4 | mww | -5.9850 | 149.7770 | 29.0 | 0 | 0 | 0 | 0 | 0 | 0 | 35 km NE of Kandrian, Papua New Guinea |
| usp000hvf6 | 2011-03-07T00:09:36.450Z | 6.3 | mww | -10.3490 | 160.7660 | 22.0 | 0 | 1 | 0 | 0 | 0 | 0 | 126 km W of Kirakira, Solomon Islands |
| usp000huvq | 2011-02-21T23:51:42.350Z | 6.1 | mww | -43.5830 | 172.6800 | 5.9 | 0 | 18 | 0 | 0 | 0 | 0 | 6 km SE of Christchurch, New Zealand |
| usp000huus | 2011-02-21T10:57:52.410Z | 6.5 | mww | -26.1420 | 178.3940 | 558.1 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| usp000huje | 2011-02-15T13:33:53.180Z | 6.1 | mww | -2.4970 | 121.4830 | 16.2 | 0 | 0 | 0 | 0 | 0 | 0 | 146 km SSE of Poso, Indonesia |
| usp000huac | 2011-02-10T14:41:58.820Z | 6.6 | mwb | 4.0770 | 123.0390 | 525.0 | 0 | 0 | 0 | 0 | 0 | 0 | 250 km SSE of Tabiauan, Philippines |
| usp000huab | 2011-02-10T14:39:27.710Z | 6.5 | mww | 4.1950 | 122.9740 | 523.2 | 0 | 0 | 0 | 0 | 0 | 0 | 235 km SSE of Tabiauan, Philippines |
| usp000hu76 | 2011-02-07T19:53:42.910Z | 6.4 | mww | -7.1540 | 155.1840 | 415.0 | 0 | 0 | 0 | 0 | 0 | 0 | 98 km SSW of Panguna, Papua New Guinea |
| usp000htp9 | 2011-01-26T15:42:29.590Z | 6.1 | mww | 2.2050 | 96.8290 | 23.0 | 0 | 0 | 0 | 0 | 0 | 0 | 58 km ESE of Sinabang, Indonesia |
| usp000ht9g | 2011-01-17T19:20:57.210Z | 6.0 | mww | -5.0300 | 102.6470 | 36.0 | 0 | 0 | 0 | 0 | 0 | 0 | 129 km SSW of Pagar Alam, Indonesia |
| usp000ht15 | 2011-01-13T16:16:41.540Z | 7.0 | mww | -20.6280 | 168.4710 | 9.0 | 0 | 3 | 0 | 0 | 0 | 0 | 118 km NNE of Tadine, New Caledonia |
| usp000hsua | 2011-01-09T17:21:51.650Z | 6.1 | mww | -19.2010 | 168.1550 | 18.0 | 0 | 4 | 0 | 0 | 0 | 0 | 124 km WNW of Isangel, Vanuatu |
| usp000hst4 | 2011-01-09T10:03:43.990Z | 6.5 | mww | -19.1550 | 168.3120 | 22.0 | 0 | 4 | 0 | 0 | 0 | 0 | 110 km WNW of Isangel, Vanuatu |
| usp000hskt | 2011-01-05T06:46:14.630Z | 6.1 | mww | -22.2600 | 171.6310 | 112.2 | 0 | 0 | 0 | 0 | 0 | 0 | southeast of the Loyalty Islands |
| usp000hs82 | 2010-12-29T06:54:19.640Z | 6.4 | mwc | -19.6610 | 168.1400 | 16.0 | 0 | 4 | 0 | 0 | 0 | 0 | 120 km W of Isangel, Vanuatu |
| usp000hrzt | 2010-12-26T02:13:37.680Z | 6.0 | mwb | -19.6160 | 168.2840 | 13.0 | 0 | 4 | 0 | 0 | 0 | 0 | 105 km W of Isangel, Vanuatu |
| usp000hrw0 | 2010-12-25T13:16:37.000Z | 7.3 | mwc | -19.7020 | 167.9470 | 16.0 | 0 | 4 | 0 | 0 | 0 | 0 | 141 km W of Isangel, Vanuatu |
| usp000hqyf | 2010-12-15T11:29:30.840Z | 6.0 | mwc | -7.2680 | 128.7860 | 134.9 | 0 | 0 | 0 | 0 | 0 | 0 | 241 km NE of Lospalos, Timor Leste |
| usp000hqvf | 2010-12-13T01:14:42.320Z | 6.2 | mwc | -6.5340 | 155.6470 | 135.8 | 0 | 0 | 0 | 0 | 0 | 0 | 30 km SE of Panguna, Papua New Guinea |
| usp000hqdx | 2010-12-02T03:12:09.820Z | 6.6 | mwb | -6.0010 | 149.9770 | 33.0 | 0 | 0 | 0 | 0 | 0 | 0 | 52 km ENE of Kandrian, Papua New Guinea |
| usp000hq00 | 2010-11-23T09:01:06.860Z | 6.1 | mwc | -5.9590 | 148.9660 | 68.0 | 0 | 1 | 0 | 0 | 0 | 0 | 69 km WNW of Kandrian, Papua New Guinea |
| usp000hpc0 | 2010-11-10T04:05:24.410Z | 6.5 | mwc | -45.4640 | 96.3940 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast Indian Ridge |
| usp000hnyy | 2010-11-03T11:18:15.570Z | 6.0 | mwc | -4.6170 | 134.0710 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 184 km NE of Tual, Indonesia |
| usp000hnjs | 2010-10-25T19:37:31.150Z | 6.3 | mwc | -2.9580 | 100.3720 | 26.0 | 0 | 1 | 0 | 0 | 0 | 0 | 150 km SW of Sungai Penuh, Indonesia |
| usp000hnj4 | 2010-10-25T14:42:22.460Z | 7.8 | mwc | -3.4870 | 100.0820 | 20.1 | 0 | 1 | 0 | 0 | 0 | 0 | 215 km SW of Sungai Penuh, Indonesia |
| usp000hmsx | 2010-10-08T05:43:08.070Z | 6.2 | mwc | 2.8310 | 128.2170 | 120.0 | 0 | 0 | 0 | 0 | 0 | 0 | 124 km N of Tobelo, Indonesia |
| usp000hmbq | 2010-09-29T17:11:25.940Z | 7.0 | mwc | -4.9630 | 133.7600 | 26.0 | 0 | 0 | 0 | 0 | 0 | 0 | Near the south coast of Papua, Indonesia |
| usp000hmbp | 2010-09-29T17:10:51.080Z | 6.2 | mb | -4.9090 | 133.7120 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 132 km NE of Tual, Indonesia |
| usp000hm7a | 2010-09-26T12:12:41.710Z | 6.0 | mwc | -5.3140 | 133.9170 | 30.0 | 0 | 0 | 0 | 0 | 0 | 0 | 133 km ENE of Tual, Indonesia |
| usp000hkew | 2010-09-08T11:37:31.890Z | 6.3 | mwc | -20.6710 | 169.8180 | 10.0 | 0 | 0 | 0 | 0 | 0 | 0 | 137 km SSE of Isangel, Vanuatu |
| usp000hk46 | 2010-09-03T16:35:47.770Z | 7.0 | mwc | -43.5220 | 171.8300 | 12.0 | 0 | 21 | 0 | 0 | 0 | 0 | 19 km NE of Methven, New Zealand |
| usp000hjh9 | 2010-08-20T17:56:14.150Z | 6.1 | mwc | -6.5700 | 154.2460 | 19.0 | 0 | 0 | 0 | 0 | 0 | 0 | 139 km WSW of Panguna, Papua New Guinea |
| usp000hj8s | 2010-08-15T15:09:29.240Z | 6.3 | mwb | -5.6920 | 148.3420 | 174.7 | 0 | 1 | 0 | 0 | 0 | 0 | 110 km NNE of Finschhafen, Papua New Guinea |
| usp000hhuc | 2010-08-10T05:23:44.980Z | 7.3 | mwc | -17.5410 | 168.0690 | 25.0 | 0 | 4 | 0 | 0 | 0 | 0 | 33 km NW of Port-Vila, Vanuatu |
| usp000hhhx | 2010-08-04T22:01:43.620Z | 7.0 | mww | -5.7460 | 150.7650 | 44.0 | 0 | 0 | 0 | 0 | 0 | 0 | 72 km ESE of Kimbe, Papua New Guinea |
| usp000hhfk | 2010-08-04T07:15:33.510Z | 6.5 | mwc | -5.4860 | 146.8220 | 220.0 | 0 | 1 | 0 | 0 | 0 | 0 | 118 km ESE of Madang, Papua New Guinea |
| usp000hhe9 | 2010-08-03T12:08:25.950Z | 6.3 | mwc | 1.2390 | 126.2130 | 41.0 | 0 | 0 | 0 | 0 | 0 | 0 | 139 km WNW of Ternate, Indonesia |
| usp000hgeq | 2010-07-22T05:03:56.440Z | 6.1 | mwc | -15.1320 | 168.1620 | 6.0 | 0 | 4 | 0 | 0 | 0 | 0 | 115 km ENE of Luganville, Vanuatu |
| usp000hgaq | 2010-07-21T09:16:04.420Z | 6.1 | mwc | 3.0390 | 128.2220 | 100.0 | 0 | 0 | 0 | 0 | 0 | 0 | 146 km N of Tobelo, Indonesia |
| usp000hg73 | 2010-07-20T19:18:20.370Z | 6.3 | mwc | -5.9020 | 150.7120 | 24.0 | 0 | 0 | 0 | 0 | 0 | 0 | 74 km ESE of Kimbe, Papua New Guinea |
| usp000hfku | 2010-07-18T13:34:59.360Z | 7.3 | mwc | -5.9310 | 150.5900 | 35.0 | 0 | 0 | 0 | 0 | 0 | 0 | New Britain region, Papua New Guinea |
| usp000hfka | 2010-07-18T13:04:09.410Z | 6.9 | mwc | -5.9660 | 150.4280 | 28.0 | 0 | 0 | 0 | 0 | 0 | 0 | 56 km SE of Kimbe, Papua New Guinea |
| usp000het5 | 2010-07-02T06:04:03.130Z | 6.3 | mwc | -13.6430 | 166.4850 | 29.0 | 0 | 0 | 0 | 0 | 0 | 0 | 118 km WNW of Sola, Vanuatu |
| usp000heqb | 2010-06-30T04:31:02.160Z | 6.4 | mwb | -23.3070 | 179.1160 | 581.4 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Fiji Islands |
| usp000hej3 | 2010-06-26T05:30:19.490Z | 6.7 | mwc | -10.6270 | 161.4470 | 35.0 | 0 | 1 | 0 | 0 | 0 | 0 | 55 km WSW of Kirakira, Solomon Islands |
| usp000hef3 | 2010-06-24T05:32:27.400Z | 6.1 | mwb | -5.5140 | 151.1610 | 40.0 | 0 | 0 | 0 | 0 | 0 | 0 | 113 km E of Kimbe, Papua New Guinea |
| usp000he6x | 2010-06-17T13:06:46.590Z | 6.0 | mwb | -33.1680 | 179.7190 | 170.4 | 0 | 0 | 0 | 0 | 0 | 0 | south of the Kermadec Islands |
| usp000he3n | 2010-06-16T03:58:08.480Z | 6.6 | mwc | -2.3290 | 136.4840 | 10.5 | 0 | 0 | 0 | 0 | 0 | 0 | 135 km SSE of Biak, Indonesia |
| usp000he3f | 2010-06-16T03:16:27.550Z | 7.0 | mwc | -2.1740 | 136.5430 | 18.0 | 0 | 0 | 0 | 0 | 0 | 0 | 121 km SSE of Biak, Indonesia |
| usp000he3d | 2010-06-16T03:06:02.420Z | 6.2 | mwb | -2.3860 | 136.6350 | 13.0 | 0 | 0 | 0 | 0 | 0 | 0 | 147 km SSE of Biak, Indonesia |
| usp000hdsf | 2010-06-09T23:23:17.350Z | 6.0 | mwb | -18.5970 | 169.4850 | 12.0 | 0 | 4 | 0 | 0 | 0 | 0 | 106 km NNE of Isangel, Vanuatu |
| usp000hd8v | 2010-05-27T20:48:00.440Z | 6.1 | mwc | -13.6580 | 166.7450 | 35.0 | 0 | 0 | 0 | 0 | 0 | 0 | 90 km WNW of Sola, Vanuatu |
| usp000hd84 | 2010-05-27T17:14:46.570Z | 7.2 | mwc | -13.6980 | 166.6430 | 31.0 | 0 | 0 | 0 | 0 | 0 | 0 | 100 km WNW of Sola, Vanuatu |
| usp000hchk | 2010-05-09T05:59:41.620Z | 7.2 | mwc | 3.7480 | 96.0180 | 38.0 | 0 | 0 | 0 | 0 | 0 | 0 | 45 km SSW of Meulaboh, Indonesia |
| usp000hcbx | 2010-05-05T16:29:03.210Z | 6.5 | mwc | -4.0540 | 101.0960 | 27.0 | 0 | 0 | 0 | 0 | 0 | 0 | 132 km WSW of Bengkulu, Indonesia |
| usp000hbug | 2010-04-24T07:41:00.410Z | 6.0 | mwc | -1.9120 | 128.1220 | 27.0 | 0 | 0 | 0 | 0 | 0 | 0 | 181 km NNW of Amahai, Indonesia |
| usp000hbjw | 2010-04-17T23:15:22.020Z | 6.2 | mwc | -6.6690 | 147.2910 | 53.0 | 0 | 1 | 0 | 0 | 0 | 0 | 33 km E of Lae, Papua New Guinea |
| usp000hb6a | 2010-04-11T09:40:25.600Z | 6.9 | mwc | -10.8780 | 161.1160 | 21.0 | 0 | 1 | 0 | 0 | 0 | 0 | 99 km WSW of Kirakira, Solomon Islands |
| usp000havw | 2010-04-07T14:33:01.930Z | 6.0 | mwc | -3.7600 | 141.9430 | 23.0 | 0 | 0 | 0 | 0 | 0 | 0 | 82 km SSW of Aitape, Papua New Guinea |
| usp000hat0 | 2010-04-06T22:15:01.580Z | 7.8 | mwc | 2.3830 | 97.0480 | 31.0 | 0 | 0 | 0 | 0 | 0 | 0 | 75 km E of Sinabang, Indonesia |
| usp000hahs | 2010-04-05T10:05:44.630Z | 6.2 | mww | -0.1830 | 125.0090 | 25.0 | 0 | 0 | 0 | 0 | 0 | 0 | 164 km S of Tondano, Indonesia |
| usp000h9ra | 2010-03-20T14:00:49.980Z | 6.6 | mwc | -3.3610 | 152.2450 | 414.6 | 0 | 0 | 0 | 0 | 0 | 0 | New Ireland region, Papua New Guinea |
| usp000h9br | 2010-03-14T00:57:44.700Z | 6.4 | mwb | -1.6920 | 128.1350 | 53.0 | 0 | 0 | 0 | 0 | 0 | 0 | 202 km NNW of Amahai, Indonesia |
| usp000h8s3 | 2010-03-05T16:07:00.680Z | 6.8 | mwc | -3.7620 | 100.9910 | 26.0 | 0 | 0 | 0 | 0 | 0 | 0 | 141 km W of Bengkulu, Indonesia |
| usp000h8pu | 2010-03-04T14:02:27.550Z | 6.5 | mwb | -13.5710 | 167.2270 | 176.0 | 0 | 0 | 0 | 0 | 0 | 0 | 48 km NW of Sola, Vanuatu |
| usp000h7bg | 2010-02-15T21:51:47.790Z | 6.2 | mwc | -7.2170 | 128.7230 | 126.0 | 0 | 0 | 0 | 0 | 0 | 0 | 238 km NE of Lospalos, Timor Leste |
| usp000h6z1 | 2010-02-05T06:59:05.500Z | 6.2 | mwc | -47.9110 | 99.5930 | 1.0 | 0 | 0 | 0 | 0 | 0 | 0 | southeast Indian Ridge |
| usp000h6v7 | 2010-02-01T22:28:16.920Z | 6.2 | mwc | -6.1120 | 154.4630 | 32.0 | 0 | 0 | 0 | 0 | 0 | 0 | 115 km WNW of Panguna, Papua New Guinea |
| usp000h5vu | 2010-01-09T05:51:30.470Z | 6.2 | mwc | -9.1310 | 157.6260 | 12.0 | 0 | 1 | 0 | 0 | 0 | 0 | 142 km SE of Gizo, Solomon Islands |
| usp000h5rx | 2010-01-05T13:11:42.820Z | 6.0 | mwc | -9.0500 | 157.8920 | 35.0 | 0 | 1 | 0 | 0 | 0 | 0 | 155 km SE of Gizo, Solomon Islands |
| usp000h5rn | 2010-01-05T12:15:32.210Z | 6.8 | mwc | -9.0190 | 157.5510 | 15.4 | 0 | 1 | 0 | 0 | 0 | 0 | 127 km SE of Gizo, Solomon Islands |
| usp000h5np | 2010-01-03T22:36:25.640Z | 7.1 | mwc | -8.7830 | 157.3540 | 10.0 | 0 | 1 | 0 | 0 | 0 | 0 | 94 km SE of Gizo, Solomon Islands |
| usp000h5nd | 2010-01-03T21:48:02.870Z | 6.6 | mwc | -8.7260 | 157.4870 | 10.0 | 0 | 1 | 0 | 0 | 0 | 0 | 98 km SE of Gizo, Solomon Islands |
