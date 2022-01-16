meta:
  id: zwift_profile
  application: Zwift
  title: Zwift profile protobuf
  endian: le
  imports:
    - /common/vlq_base128_le
seq:
  - id: pairs
    type: pair
    repeat: eos
types:
  pair:
    seq:
      - id: key
        type: vlq_base128_le
      - id: value
        type:
          switch-on: wire_type
          cases:
            'wire_types::varint': vlq_base128_le
            'wire_types::len_delimited': delimited_bytes
            'wire_types::bit_64': u8le
            'wire_types::bit_32': u4le
    instances:
      wire_type:
        value: 'key.value & 0b111'
        enum: wire_types
      field_tag:
        value: 'key.value >> 3'
    enums:
      wire_types:
        0: varint
        1: bit_64
        2: len_delimited
        3: group_start
        4: group_end
        5: bit_32
  delimited_bytes:
    seq:
      - id: len
        type: vlq_base128_le
      - id: body
        size: len.value
        type:
          switch-on: _parent.field_tag
          cases:
            33: f33
  f33:
    seq:
      - id: game_saves
        type: game_save
        repeat: until
        repeat-until: _.id == game_save::id::end_mark5
  game_save:
    seq:
      - id: id
        type: u4
        enum: id
      - id: length
        type: u4
      - id: data
        type:
          switch-on: id
          cases:
            'id::tracking16_var': t_tracking
            _: t_simple
    enums:
      id:
        0x10000001: accessories1_100   #2048bit=0x100 bytes, for example "Humans/Accessories/Gloves/ZwiftKOMGloves01.xml" maps to bit 318
        0x1000000B: accessories1r_100  #=save_type1_100 on read, not saved

        0x10000002: save_type2_40      #512bit = 0x40 (all 0)
        0x1000000C: save_type2r_40     #=save_type2_40 on read, not saved

        0x10000006: save_type6_var     #garage?

        0x10000009: save_type9_50      #(all 0)

        0x10000007: save_type7_40      #512bit = 0x40 (all 0)
        0x1000000D: save_type7r_40     #=save_type7_040on read, not saved

        0x1000000F: achiev15_var       #AchievementManager chunks

        0x10000010: tracking16_var     #TrackingData

        0x10000011: old_goals17r_var   #old goals data format

        0x10000005: end_mark5          #mark end of all savings, no data
  t_simple:
    seq:
      - id: data
        size: _parent.length - 8
  t_tracking:
    seq:
      - id: count
        type: u4
      - id: data
        type: t_track_item
        repeat: expr
        repeat-expr: count
  t_track_item:
    seq:
      - id: id
        type: u4
        enum: id
      - id: t_id
        type: u4
        enum: t_id
      - id: u4_val
        type: u4
      - id: f4_val
        type: f4
    enums:
      t_id:
        1: float
        2: int
        3: byte
      id:
        0x9e2c6328: pool_size # "PoolSize"
        0xe8ed6e3d: swimming_pace_0 # "SwimmingPace_0"
        0x9fea5eab: swimming_pace_1 # "SwimmingPace_1"
        0x06e30f11: swimming_pace_2 # "SwimmingPace_2"
        0x71e43f87: swimming_pace_3 # "SwimmingPace_3"
        0xef80aa24: swimming_pace_4 # "SwimmingPace_4"
        0x836cff9c: running_pace_1mi # "RunningPace_1mi"
        0xd55234df: running_pace_5km # "RunningPace_5km"
        0x4e699e99: running_pace_10km # "RunningPace_10km"
        0xdb69cd45: running_pace_hm # "RunningPace_hm"
        0x45eae0cb: running_pace_fm # "RunningPace_fm"
        0xe795b583: running_pace_1mi_estimated # "RunningPace_1mi_estimated"
        0x78c80977: running_pace_5km_estimated # "RunningPace_5km_estimated"
        0xaf8e1b0f: running_pace_10km_estimated # "RunningPace_10km_estimated"
        0x1c8c50e0: running_pace_hm_estimated # "RunningPace_hm_estimated"
        0xf5bd83fe: running_pace_fm_estimated # "RunningPace_fm_estimated"
        0x560fcbd5: use_skill_levelrunning # "UseSkillLevelRunning"
        0xb2fd90ee: use_skill_levelcycling # "UseSkillLevelCycling"
        0xec37cb97: cycling_skill_level # "CyclingSkillLevel"
        0xc682fcc0: running_skill_level # "RunningSkillLevel"
        0x598443fb: completed_any_workout # "COMPLETEDANYWORKOUT"
        0x5b66cc9c: scotty_watching_tutorial_1 # "SCOTTY_WATCHING_TUTORIAL_1"
        0x424ea4d3: scotty_leaderboard_tutorial # "SCOTTY_LEADERBOARD_TUTORIAL"
        0xe6bb413b: scotty_ridersnearby_tutorial # "SCOTTY_RIDERSNEARBY_TUTORIAL"
        0xbf79811f: mixtape_2019_1 # "MIXTAPE_2019_1"
        0x2670d0a5: mixtape_2019_2 # "MIXTAPE_2019_2"
        0x5177e033: mixtape_2019_3 # "MIXTAPE_2019_3"
        0xcf137590: mixtape_2019_4 # "MIXTAPE_2019_4"
        0xb8144506: mixtape_2019_5 # "MIXTAPE_2019_5"
        0x211d14bc: mixtape_2019_6 # "MIXTAPE_2019_6"
        0x561a242a: mixtape_2019_7 # "MIXTAPE_2019_7"
        0xc6a539bb: mixtape_2019_8 # "MIXTAPE_2019_8"
        0x34f647b2: spinwheel_spincount # "SPINWHEEL_SPINCOUNT"
        0xe412bb7b: current_eula_version # "CURRENT_EULA_VERSION"
        0x2ea8df6a: rode_with_zml # "RODE_WITH_ZML"
        0x5ef9ad14: zar2021 # "ZAR2021"
        0xdaa16f19: rfto2021 # "RFTO2021"
        0xc72b3ccd: pacerbot_dropin_clicked # "PACERBOTDROPINCLICKED"
        0xfea634fb: scotty_dropin_tutorial_01 # "SCOTTY_DROPIN_TUTORIAL_01"
        0x67af6541: scotty_dropin_tutorial_02 # "SCOTTY_DROPIN_TUTORIAL_02"
        0x10a855d7: scotty_dropin_tutorial_03 # "SCOTTY_DROPIN_TUTORIAL_03"
        0x8eccc074: scotty_dropin_tutorial_04 # "SCOTTY_DROPIN_TUTORIAL_04"
        0xf9cbf0e2: scotty_dropin_tutorial_05 # "SCOTTY_DROPIN_TUTORIAL_05"
        0x60c2a158: scotty_dropin_tutorial_06 # "SCOTTY_DROPIN_TUTORIAL_06"
        0x17c591ce: scotty_dropin_tutorial_07 # "SCOTTY_DROPIN_TUTORIAL_07"
        0xd83c4c7a: scotty_pairing_outro # "SCOTTY_PAIRING_OUTRO"
        0xd0646944: scotty_pairing_intro # "SCOTTY_PAIRING_INTRO"
        0x2cebca4b: setup_profile_info # "SETUPPROFILEINFO"
        0xb6061fba: current_route_version # "CURRENTROUTEVERSION"
        0x06880226: android_setup_region # "ANDROID_SETUPREGION"
        0x0509c9a9: last_zml_advert_time # "LAST_ZML_ADVERT_TIME"
        0xd21df098: completed_orientation_ride # "COMPLETEDORIENTATIONRIDE"
        0xeebaf1fd: completed_welcome_ride # "COMPLETEDWELCOMERIDE"