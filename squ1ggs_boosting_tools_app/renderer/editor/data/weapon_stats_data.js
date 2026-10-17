const WEAPON_STATS_DATA = {
  "Dad_UB_AmmoSwitcher_Init": {
    "table_name": "Dad_UB_AmmoSwitcher_Init",
    "rows": {
      "Pistol": {
        "zoomduration_scale": 0.7,
        "putdowntime_scale": 0.7,
        "equiptime_scale": 0.7,
        "maxaccuracy_scale": 1.1,
        "spread_scale": 0.9,
        "reloadtime_scale": 0.85,
        "firerate_scale": 1.1,
        "damage_scale": 0.95
      },
      "AssaultRifle": {
        "recoil_scale": 1.05,
        "maxaccuracy_scale": 0.85,
        "spread_scale": 0.9,
        "firerate_scale": 0.9,
        "damage_scale": 1.1
      },
      "SMG": {
        "recoil_scale": 0.8,
        "accimpulse_scale": 1.25,
        "maxaccuracy_scale": 0.8,
        "spread_scale": 1.25,
        "firerate_scale": 1.25,
        "damage_scale": 0.9
      },
      "Shotgun": {
        "ammocost_add": 1.0,
        "projpershot_scale": 3.0,
        "recoil_scale": 1.25,
        "accimpulse_scale": 1.1,
        "maxaccuracy_scale": 0.65,
        "spread_scale": 2.0,
        "firerate_scale": 0.8,
        "damage_scale": 0.6
      },
      "Sniper": {
        "critdamage_add": 0.35,
        "recoil_scale": 1.4,
        "maxaccuracy_scale": 0.6,
        "spread_scale": 0.6,
        "firerate_scale": 0.75,
        "damage_scale": 1.3
      },
      "Base_Pistol": {
        "zoomduration_scale": 1.35,
        "putdowntime_scale": 1.35,
        "equiptime_scale": 1.35,
        "maxaccuracy_scale": 0.9,
        "spread_scale": 1.1,
        "reloadtime_scale": 1.2,
        "firerate_scale": 0.9,
        "damage_scale": 1.1
      },
      "Base_AssaultRifle": {
        "recoil_scale": 0.95,
        "maxaccuracy_scale": 1.15,
        "spread_scale": 1.1,
        "firerate_scale": 1.1,
        "damage_scale": 0.9
      },
      "Base_SMG": {
        "recoil_scale": 1.25,
        "accimpulse_scale": 0.8,
        "maxaccuracy_scale": 1.25,
        "spread_scale": 0.8,
        "firerate_scale": 0.8,
        "damage_scale": 1.075
      },
      "Base_Sniper": {
        "critdamage_add": -0.35,
        "recoil_scale": 0.7,
        "maxaccuracy_scale": 1.65,
        "spread_scale": 1.65,
        "firerate_scale": 1.35,
        "damage_scale": 0.825
      },
      "Base_Shotgun": {
        "projpershot_scale": 0.5,
        "recoil_scale": 0.8,
        "accimpulse_scale": 0.9,
        "maxaccuracy_scale": 1.5,
        "spread_scale": 0.5,
        "firerate_scale": 1.1,
        "damage_scale": 1.75
      },
      "Base_Shotgun_Maliwan": {
        "recoil_scale": 0.8,
        "accimpulse_scale": 0.9,
        "maxaccuracy_scale": 1.5,
        "spread_scale": 0.5,
        "firerate_scale": 1.1,
        "damage_scale": 0.875
      }
    }
  },
  "Economy_WeaponScales": {
    "table_name": "Economy_WeaponScales",
    "rows": {
      "Barrel_Acc_Default": {
        "none": 1.05
      },
      "Barrel_Acc_Licensed_Hyp": {
        "none": 1.1
      },
      "Barrel_Acc_Licensed_Jak": {
        "none": 1.2
      },
      "Barrel_Acc_Licensed_Ted": {
        "none": 1.2
      },
      "Body_Acc": {
        "none": 1.05
      },
      "Grip_Licensed_Hyp": {
        "none": 1.1
      },
      "Grip_Licensed_Ted": {
        "none": 1.15
      },
      "Mag_Licensed_Bor": {
        "none": 1.2
      },
      "Mag_Licensed_Cov": {
        "none": 1.2
      },
      "Mag_Licensed_Tor": {
        "none": 1.2
      },
      "Scope_Acc": {
        "none": 1.05
      },
      "Underbarrel_Default": {
        "none": 1.3
      },
      "Underbarrel_Licensed_Atl": {
        "none": 1.25
      },
      "Underbarrel_Licensed_Dad": {
        "none": 1.25
      },
      "Underbarrel_Licensed_Mal": {
        "none": 1.25
      },
      "Underbarrel_Acc_Vla": {
        "none": 1.05
      },
      "Element": {
        "none": 1.2
      }
    }
  },
  "Table_WeaponBorgCharge_Init": {
    "table_name": "Table_WeaponBorgCharge_Init",
    "rows": {
      "DAD_AR": {
        "dischargetime_value": 0.25
      },
      "DAD_PS": {
        "dischargetime_value": 0.25
      },
      "DAD_SG": {
        "dischargetime_value": 0.25
      },
      "DAD_SM": {
        "dischargetime_value": 0.25
      },
      "JAK_AR": {
        "dischargetime_value": 0.5
      },
      "JAK_PS": {
        "dischargetime_value": 0.6,
        "chargetime_value": 0.6
      },
      "JAK_SG": {
        "dischargetime_value": 0.5
      },
      "JAK_SR": {
        "dischargetime_value": 0.5
      },
      "BOR_SG": {
        "dischargetime_value": 0.5
      },
      "BOR_SM": {
        "dischargetime_value": 0.5
      },
      "BOR_SR": {
        "dischargetime_value": 0.5
      },
      "MAL_SG": {
        "dischargetime_value": 0.5
      },
      "MAL_SM": {
        "dischargetime_value": 0.5
      },
      "MAL_SR": {
        "dischargetime_value": 0.5
      },
      "ORD_PS": {
        "dischargetime_value": 0.5
      },
      "ORD_AR": {
        "dischargetime_value": 0.5
      },
      "ORD_SR": {
        "dischargetime_value": 0.5
      },
      "TED_AR": {
        "dischargetime_value": 0.5
      },
      "TED_PS": {
        "dischargetime_value": 0.25
      },
      "TED_SG": {
        "dischargetime_value": 0.5
      },
      "TOR_AR": {
        "dischargetime_value": 0.5
      },
      "TOR_PS": {
        "dischargetime_value": 0.5
      },
      "TOR_SG": {
        "dischargetime_value": 0.5
      },
      "VLA_AR": {
        "dischargetime_value": 0.5
      },
      "VLA_SM": {
        "dischargetime_value": 0.5
      },
      "VLA_SR": {
        "dischargetime_value": 0.5
      }
    }
  },
  "terminal_rarity_init": {
    "table_name": "terminal_rarity_init",
    "rows": {
      "Common": {
        "potency": 0.0,
        "radius": 0.0,
        "cooldown": 0.0,
        "duration": 0.0,
        "custom": 0.0
      },
      "Uncommon": {
        "potency": 0.1,
        "radius": 0.1,
        "cooldown": -0.1,
        "duration": 0.1,
        "custom": 0.0
      },
      "Rare": {
        "potency": 0.2,
        "radius": 0.2,
        "cooldown": -0.2,
        "duration": 0.2,
        "custom": 0.0
      },
      "Epic": {
        "potency": 0.3,
        "radius": 0.3,
        "cooldown": -0.3,
        "duration": 0.3,
        "custom": 0.0
      },
      "Legendary": {
        "potency": 0.3,
        "radius": 0.3,
        "cooldown": -0.3,
        "duration": 0.3,
        "custom": 0.0
      }
    }
  },
  "Unique_AR_Barrel_Init": {
    "table_name": "Unique_AR_Barrel_Init",
    "rows": {
      "VLA_WomboCombo": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "accregen_value": -4.0,
        "accimpulse_value": 0.35,
        "accuracy_value": 3.5,
        "spread_value": 2.5,
        "firerate_value": 12.0,
        "damage_scale": 1.3
      },
      "DAD_Lumberjack": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "accregen_value": -5.5,
        "accimpulse_value": 0.27,
        "accuracy_value": 3.8,
        "spread_value": 2.0,
        "firerate_value": 4.0,
        "damage_scale": 2.2
      },
      "TOR_Bugbear": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "damageradius_value": 50.0,
        "accregen_value": -5.0,
        "accimpulse_value": 0.3,
        "accuracy_value": 3.75,
        "spread_value": 2.5,
        "firerate_value": 5.5,
        "damage_scale": 1.8
      },
      "ORD_Goalkeeper": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "accregen_value": -6.0,
        "accimpulse_value": 0.55,
        "accuracy_value": 4.0,
        "spread_value": 1.1,
        "firerate_value": 7.0,
        "damage_scale": 4.0
      },
      "JAK_BonnieClyde": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "recoil_scale": 0.75,
        "accdelay_value": 0.25,
        "accimpulse_value": 0.7,
        "accuracy_value": 6.5,
        "spread_value": 2.0,
        "firerate_value": 6.25,
        "damage_scale": 3.6
      },
      "VLA_Lucian": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "sway_scale": 1.2,
        "accregen_value": -4.0,
        "accimpulse_value": 0.35,
        "accuracy_value": 3.5,
        "spread_value": 2.75,
        "firerate_value": 11.5,
        "damage_scale": 0.975
      },
      "JAK_Rowan": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "recoil_scale": 0.6,
        "accregen_value": -10.0,
        "accdelay_value": 0.2,
        "accimpulse_value": 0.75,
        "accuracy_value": 5.5,
        "spread_value": 2.0,
        "firerate_value": 3.0,
        "damage_scale": 3.4
      },
      "VLA_DualDamage": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "sway_scale": 1.2,
        "accregen_value": -4.0,
        "accimpulse_value": 0.35,
        "accuracy_value": 3.5,
        "spread_value": 2.75,
        "firerate_value": 12.5
      },
      "TED_Chuck": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "accregen_value": -8.5,
        "accdelay_value": 0.4,
        "accimpulse_value": 0.3,
        "accuracy_value": 4.5,
        "spread_value": 2.75,
        "firerate_value": 3.4,
        "damage_scale": 2.0
      },
      "DAD_StarHelix": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "accimpulse_value": 0.1,
        "accuracy_value": 3.6,
        "spread_value": 3.0,
        "firerate_value": 3.5,
        "damage_scale": 2.0
      },
      "TOR_PotatoThrower": {
        "part_value": 1.0,
        "impact_force_value": 45000.0,
        "damageradius_value": 135.0,
        "accimpulse_value": 0.5,
        "accuracy_value": 4.0,
        "spread_value": 2.5,
        "firerate_value": 5.5,
        "damage_scale": 1.3
      },
      "ORD_GMR": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "recoil_scale": 0.6,
        "accregen_value": -6.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 3.5,
        "spread_value": 1.75,
        "firerate_value": 4.0,
        "damage_scale": 4.5
      },
      "DAD_OM": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "sway_scale": 1.4,
        "accimpulse_value": 0.32,
        "accuracy_value": 4.75,
        "spread_value": 2.75,
        "firerate_value": 6.75,
        "damage_scale": 1.14
      },
      "VLA_WF": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "sway_scale": 0.8,
        "recoil_scale": 0.95,
        "accregen_value": -6.0,
        "accuracy_value": 4.5,
        "spread_value": 1.85,
        "firerate_value": 12.25,
        "damage_scale": 1.9
      },
      "TED_DividedFocus": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "recoil_scale": 0.8,
        "accregen_value": -9.0,
        "accdelay_value": 0.4,
        "accimpulse_value": 0.3,
        "accuracy_value": 5.5,
        "spread_value": 3.5,
        "firerate_value": 4.0,
        "damage_scale": 2.5
      },
      "JAK_Screenwriter": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "sway_scale": 3.0,
        "recoil_scale": 0.75,
        "accdelay_value": 0.25,
        "accimpulse_value": 0.7,
        "accuracy_value": 4.0,
        "spread_value": 5.0,
        "firerate_value": 8.0
      },
      "TOR_ColdShoulder": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "damageradius_value": 50.0,
        "accregen_value": -5.0,
        "accimpulse_value": 0.3,
        "accuracy_value": 3.75,
        "spread_value": 2.5,
        "firerate_value": 5.5,
        "damage_scale": 1.8
      },
      "DAD_FirstImpression": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "sway_scale": 1.4,
        "accimpulse_value": 0.32,
        "accuracy_value": 4.3,
        "spread_value": 2.55,
        "firerate_value": 6.75,
        "damage_scale": 1.28
      }
    }
  },
  "Unique_PS_Barrel_Init": {
    "table_name": "Unique_PS_Barrel_Init",
    "rows": {
      "ORD_Bully": {
        "part_value": 2.0,
        "impact_force_value": 50000.0,
        "sway_scale": 0.5,
        "recoil_scale": 0.25,
        "accregen_value": -6.5,
        "accimpulse_value": 0.75,
        "accuracy_value": 5.0,
        "spread_value": 1.25,
        "firerate_value": 7.0,
        "damage_scale": 2.0
      },
      "TOR_Roach": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "damageradius_value": 25.0,
        "accdelay_value": 0.6,
        "accimpulse_value": 1.0,
        "accuracy_value": 3.0,
        "spread_value": 3.0,
        "firerate_value": 2.2,
        "damage_scale": 3.0
      },
      "DAD_Zipgun": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "sway_scale": 1.15,
        "accregen_value": -5.0,
        "accdelay_value": 0.4,
        "accimpulse_value": 0.225,
        "accuracy_value": 3.0,
        "spread_value": 3.15,
        "firerate_value": 20.0,
        "damage_scale": 1.55
      },
      "JAK_SeventhSense": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "recoil_scale": 0.8,
        "accdelay_value": 0.28,
        "accimpulse_value": 0.6,
        "accuracy_value": 3.75,
        "spread_value": 3.5,
        "firerate_value": 9.0,
        "damage_scale": 4.0
      },
      "JAK_KingsGambit": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "accregen_value": -10.0,
        "accdelay_value": 0.45,
        "accimpulse_value": 0.8,
        "accuracy_value": 5.5,
        "spread_value": 2.75,
        "firerate_value": 7.5,
        "damage_scale": 4.2
      },
      "ORD_NoisyCricket": {
        "damageradius_value": 400.0,
        "accimpulse_value": 0.5,
        "accuracy_value": 4.0,
        "spread_value": 2.0,
        "firerate_value": 3.0,
        "damage_scale": 10.0
      },
      "TOR_QueensRest": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "damageradius_value": 135.0,
        "accdelay_value": 0.6,
        "accimpulse_value": 1.5,
        "accuracy_value": 3.5,
        "spread_value": 1.8,
        "firerate_value": 1.75,
        "damage_scale": 5.0
      },
      "ORD_RocketReload": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "accregen_value": -6.5,
        "accimpulse_value": 1.0,
        "accuracy_value": 7.0,
        "spread_value": 1.5,
        "firerate_value": 6.5,
        "damage_scale": 2.0
      },
      "JAK_PhantomFlame": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "recoil_scale": 0.8,
        "accregen_value": -4.0,
        "accdelay_value": 0.28,
        "accimpulse_value": 2.0,
        "accuracy_value": 6.0,
        "spread_value": 5.0,
        "firerate_value": 9.0,
        "damage_scale": 5.0
      },
      "TED_Sideshow": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "accregen_value": -6.5,
        "accdelay_value": 0.35,
        "accimpulse_value": 0.35,
        "accuracy_value": 7.0,
        "spread_value": 1.0,
        "firerate_value": 3.0
      },
      "TED_BIRD": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "accregen_value": -8.25,
        "accdelay_value": 0.4,
        "accimpulse_value": 0.3,
        "accuracy_value": 3.75,
        "spread_value": 4.5,
        "firerate_value": 4.8,
        "damage_scale": 1.8
      },
      "DAD_rangefinder": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "damageradius_value": 50.0,
        "recoil_scale": 1.5,
        "accregen_value": -6.0,
        "accdelay_value": 0.45,
        "accimpulse_value": 0.175,
        "accuracy_value": 3.0,
        "spread_value": 1.8,
        "firerate_value": 12.0,
        "damage_scale": 1.4
      },
      "TED_ATLien": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "accregen_value": -8.25,
        "accdelay_value": 0.4,
        "accimpulse_value": 0.3,
        "accuracy_value": 3.75,
        "spread_value": 4.5,
        "firerate_value": 4.8,
        "damage_scale": 1.8
      },
      "TED_RubysGrasp": {
        "accuracy_value": 3.75,
        "spread_value": 3.5,
        "firerate_value": 5.75
      },
      "JAK_Quickdraw": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "accregen_value": -10.0,
        "accdelay_value": 0.45,
        "accimpulse_value": 0.8,
        "accuracy_value": 4.0,
        "spread_value": 4.0,
        "firerate_value": 7.5,
        "damage_scale": 4.2
      }
    }
  },
  "Unique_SG_Barrel_Init": {
    "table_name": "Unique_SG_Barrel_Init",
    "rows": {
      "MAL_Kaleidosplode": {
        "part_value": 1.0,
        "impact_force_value": 30000.0,
        "damageradius_value": 200.0,
        "statusdamage_scale": 1.5,
        "accregen_value": -4.0,
        "accdelay_value": 1.25,
        "accimpulse_value": 0.8,
        "accuracy_value": 3.5,
        "spread_value": 4.0,
        "firerate_value": 1.0,
        "damage_scale": 2.1
      },
      "JAK_Slugger": {
        "part_value": 1.0,
        "impact_force_value": 10000.0,
        "recoil_scale": 0.7,
        "accimpulse_value": 0.75,
        "accuracy_value": 4.0,
        "spread_value": 3.0,
        "firerate_value": 1.0,
        "damage_scale": 9.0
      },
      "TOR_Linebacker": {
        "part_value": 1.0,
        "impact_force_value": 15000.0,
        "projectilespershot_value": 4.0,
        "damageradius_value": 100.0,
        "accdelay_value": 0.9,
        "accimpulse_value": 0.9,
        "accuracy_value": 5.0,
        "spread_value": 6.0,
        "firerate_value": 1.0,
        "damage_scale": 1.4
      },
      "JAK_BonnieClyde": {
        "part_value": 1.0,
        "impact_force_value": 5000.0,
        "projectilespershot_value": 6.0,
        "accdelay_value": 0.75,
        "accimpulse_value": 1.3,
        "accuracy_value": 4.5,
        "spread_value": 4.5,
        "firerate_value": 1.2,
        "damage_scale": 1.8
      },
      "TED_Anarchy": {
        "part_value": 1.0,
        "impact_force_value": 3750.0,
        "projectilespershot_value": 12.0,
        "accdelay_value": 0.75,
        "accimpulse_value": 1.0,
        "accuracy_value": 5.0,
        "spread_value": 7.0,
        "firerate_value": 1.6,
        "damage_scale": 0.5
      },
      "DAD_HeartGun": {
        "part_value": 2.0,
        "impact_force_value": 7500.0,
        "projectilespershot_value": 14.0,
        "accimpulse_value": 0.6,
        "accuracy_value": 4.25,
        "spread_value": 6.5,
        "firerate_value": 2.0,
        "damage_scale": 0.5
      },
      "BOR_GoldenGod": {
        "part_value": 1.0,
        "impact_force_value": 7500.0,
        "projectilespershot_value": 4.0,
        "damageradius_value": 50.0,
        "accregen_value": -6.0,
        "accimpulse_value": 0.5,
        "accuracy_value": 4.0,
        "spread_value": 7.0,
        "firerate_value": 4.5,
        "damage_scale": 0.675
      },
      "BOR_Convergence": {
        "part_value": 2.0,
        "impact_force_value": 5000.0,
        "projectilespershot_value": 6.0,
        "damageradius_value": 75.0,
        "recoil_scale": 1.2,
        "accregen_value": -7.0,
        "accdelay_value": 0.7,
        "accimpulse_value": 0.7,
        "accuracy_value": 4.0,
        "spread_value": 5.5,
        "firerate_value": 3.0,
        "damage_scale": 0.5625
      },
      "DAD_Bod": {
        "part_value": 1.0,
        "impact_force_value": 5000.0,
        "projectilespershot_value": 5.0,
        "sway_scale": 1.2,
        "recoil_scale": 0.25,
        "accimpulse_value": 0.75,
        "accuracy_value": 4.0,
        "spread_value": 6.0,
        "firerate_value": 4.2,
        "damage_scale": 0.475
      },
      "MAL_Kickballer": {
        "part_value": 1.0,
        "impact_force_value": 30000.0,
        "damageradius_value": 150.0,
        "statusdamage_scale": 1.5,
        "accregen_value": -4.0,
        "accdelay_value": 1.25,
        "accimpulse_value": 0.8,
        "accuracy_value": 3.5,
        "spread_value": 4.0,
        "firerate_value": 0.8,
        "damage_scale": 9.2
      },
      "JAK_RainbowVomit": {
        "part_value": 1.0,
        "impact_force_value": 5000.0,
        "projectilespershot_value": 6.0,
        "damageradius_value": 50.0,
        "accdelay_value": 0.75,
        "accimpulse_value": 1.3,
        "accuracy_value": 4.5,
        "spread_value": 4.5,
        "firerate_value": 1.5,
        "damage_scale": 1.475
      },
      "JAK_TKsWave": {
        "part_value": 2.0,
        "impact_force_value": 9000.0,
        "projectilespershot_value": 10.0,
        "recoil_scale": 0.85,
        "accregen_value": -5.0,
        "accdelay_value": 0.9,
        "accimpulse_value": 1.7,
        "accuracy_value": 5.75,
        "spread_value": 8.75,
        "firerate_value": 1.3,
        "damage_scale": 3.0
      },
      "TOR_LeadBalloon": {
        "part_value": 2.0,
        "impact_force_value": 7500.0,
        "projectilespershot_value": 3.0,
        "damageradius_value": 135.0,
        "accdelay_value": 1.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 6.0,
        "spread_value": 5.0,
        "firerate_value": 1.8,
        "damage_scale": 2.25
      },
      "JAK_Hellwalker": {
        "part_value": 1.0,
        "impact_force_value": 5000.0,
        "projectilespershot_value": 10.0,
        "accdelay_value": 0.75,
        "accimpulse_value": 1.3,
        "accuracy_value": 4.5,
        "spread_value": 10.0,
        "firerate_value": 2.0,
        "damage_scale": 1.475
      },
      "MAL_Sweet_Embrace": {
        "part_value": 1.0,
        "impact_force_value": 15000.0,
        "projectilespershot_value": 4.0,
        "damageradius_value": 150.0,
        "statusdamage_scale": 1.5,
        "accregen_value": -4.0,
        "accdelay_value": 1.25,
        "accimpulse_value": 0.8,
        "accuracy_value": 3.5,
        "spread_value": 5.0,
        "firerate_value": 1.0,
        "damage_scale": 4.5
      },
      "BOR_GoreMaster": {
        "part_value": 2.0,
        "impact_force_value": 5000.0,
        "projectilespershot_value": 6.0,
        "damageradius_value": 75.0,
        "recoil_scale": 1.2,
        "accregen_value": -7.0,
        "accdelay_value": 0.7,
        "accimpulse_value": 0.7,
        "accuracy_value": 4.0,
        "spread_value": 5.5,
        "firerate_value": 3.0,
        "damage_scale": 0.625
      },
      "TED_CommBD": {
        "part_value": 1.0,
        "impact_force_value": 3750.0,
        "projectilespershot_value": 8.0,
        "recoil_scale": 0.2,
        "accdelay_value": 0.75,
        "accimpulse_value": 1.0,
        "accuracy_value": 5.0,
        "spread_value": 7.0,
        "firerate_value": 1.25,
        "damage_scale": 0.75
      }
    }
  },
  "Unique_SMG_Barrel_Init": {
    "table_name": "Unique_SMG_Barrel_Init",
    "rows": {
      "MAL_Katagawa": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "sway_scale": 0.25,
        "recoil_scale": 0.7,
        "accregen_value": -6.0,
        "accimpulse_value": 0.75,
        "accuracy_value": 5.0,
        "spread_value": 1.25,
        "firerate_value": 1.75,
        "damage_scale": 2.25
      },
      "DAD_Conglomerate": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "damageradius_value": 20.0,
        "sway_scale": 0.5,
        "recoil_scale": 0.8,
        "accregen_value": -7.0,
        "accimpulse_value": 0.35,
        "accuracy_value": 4.0,
        "spread_value": 3.0,
        "firerate_value": 13.0,
        "damage_scale": 1.6
      },
      "DAD_Luty": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "sway_scale": 0.8,
        "recoil_scale": 0.8,
        "accregen_value": -10.0,
        "accuracy_value": 6.5,
        "spread_value": 2.8,
        "firerate_value": 22.0
      },
      "MAL_OhmIGot": {
        "part_value": 1.0,
        "impact_force_value": 8000.0,
        "statusdamage_scale": 1.5,
        "sway_scale": 0.35,
        "recoil_scale": 0.0,
        "accregen_value": -11.0,
        "accdelay_value": 0.6,
        "accuracy_value": 3.5,
        "spread_value": 1.0,
        "firerate_value": 7.25,
        "damage_scale": 1.8
      },
      "VLA_Onslaught": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "sway_scale": 1.2,
        "recoil_scale": 0.8,
        "accregen_value": -7.0,
        "accdelay_value": 0.25,
        "accimpulse_value": 0.25,
        "accuracy_value": 6.0,
        "spread_value": 3.0,
        "firerate_value": 16.0,
        "damage_scale": 0.8
      },
      "MAL_PlasmaCoil": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "damageradius_value": 35.0,
        "statusdamage_scale": 1.5,
        "sway_scale": 0.7,
        "recoil_scale": 0.65,
        "accregen_value": -11.0,
        "accdelay_value": 0.55,
        "accimpulse_value": 0.15,
        "accuracy_value": 3.0,
        "spread_value": 2.0,
        "firerate_value": 15.0,
        "damage_scale": 2.1
      },
      "BOR_Hellfire": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "damageradius_value": 25.0,
        "statusdamage_scale": 1.5,
        "statuschance_scale": 2.0,
        "accregen_value": -6.0,
        "accdelay_value": 0.25,
        "accuracy_value": 4.5,
        "spread_value": 4.0,
        "firerate_value": 6.75,
        "damage_scale": 1.2
      },
      "BOR_Prince": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "statuschance_scale": 1.5,
        "accregen_value": -6.0,
        "accdelay_value": 0.25,
        "accuracy_value": 5.0,
        "spread_value": 3.0,
        "firerate_value": 5.5,
        "damage_scale": 1.9
      },
      "DAD_BloodStarved": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "projectilespershot_value": 2.0,
        "accuracy_value": 4.5,
        "spread_value": 3.75,
        "firerate_value": 10.0,
        "damage_scale": 1.475
      },
      "VLA_BeeGun": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "sway_scale": 1.2,
        "recoil_scale": 0.9,
        "accuracy_value": 4.75,
        "spread_value": 3.8,
        "firerate_value": 11.0,
        "damage_scale": 1.1
      },
      "VLA_Kaoson": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "projectilespershot_value": 2.0,
        "accimpulse_value": 0.1,
        "accuracy_value": 4.5,
        "spread_value": 2.25,
        "firerate_value": 10.5,
        "damage_scale": 0.9
      },
      "MAL_Firework": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "damageradius_value": 35.0,
        "statusdamage_scale": 1.5,
        "sway_scale": 1.1,
        "recoil_scale": 0.95,
        "accregen_value": -11.0,
        "accdelay_value": 0.55,
        "accimpulse_value": 0.15,
        "accuracy_value": 2.75,
        "spread_value": 1.75,
        "firerate_value": 5.25,
        "damage_scale": 2.0
      }
    }
  },
  "Unique_SR_Barrel_Init": {
    "table_name": "Unique_SR_Barrel_Init",
    "rows": {
      "MAL_Katagawa": {
        "part_value": 2.0,
        "damageradius_value": 20.0,
        "statusdamage_scale": 1.5,
        "sway_scale": 0.9,
        "recoil_scale": 0.6,
        "accdelay_value": 0.6,
        "accimpulse_value": 0.3,
        "accuracy_value": 4.0,
        "spread_value": 1.75,
        "firerate_value": 1.5,
        "damage_scale": 3.25
      },
      "JAK_Boomslang": {
        "part_value": 2.0,
        "damageradius_value": 180.0,
        "sway_scale": 0.7,
        "recoil_scale": 0.7,
        "accregen_value": -7.5,
        "accdelay_value": 0.7,
        "accimpulse_value": 0.5,
        "accuracy_value": 6.0,
        "spread_value": 0.5,
        "firerate_value": 0.8,
        "damage_scale": 13.0
      },
      "ORD_Fisheye": {
        "part_value": 1.0,
        "sway_scale": 0.1,
        "recoil_scale": 0.1,
        "critdamage_add": 0.4,
        "accregen_value": -6.0,
        "accdelay_value": 0.75,
        "accimpulse_value": 0.05,
        "accuracy_value": 4.0,
        "spread_value": 3.0,
        "firerate_value": 1.15,
        "damage_scale": 7.0
      },
      "BOR_Vamoose": {
        "part_value": 2.0,
        "sway_scale": 0.6,
        "recoil_scale": 0.6,
        "accuracy_value": 6.0,
        "spread_value": 1.2,
        "firerate_value": 9.0,
        "damage_scale": 5.0
      },
      "VLA_Finnty": {
        "part_value": 2.0,
        "sway_scale": 0.25,
        "recoil_scale": 0.25,
        "accimpulse_value": 0.25,
        "accuracy_value": 3.5,
        "spread_value": 0.9,
        "firerate_value": 13.0,
        "damage_scale": 2.0
      },
      "MAL_ComplexRoot": {
        "part_value": 1.0,
        "damageradius_value": 20.0,
        "statusdamage_scale": 1.5,
        "sway_scale": 0.5,
        "accregen_value": -4.0,
        "accdelay_value": 0.8,
        "accimpulse_value": 1.0,
        "accuracy_value": 5.0,
        "spread_value": 2.0,
        "firerate_value": 1.2,
        "damage_scale": 5.0
      },
      "ORD_Symmetry": {
        "part_value": 2.0,
        "recoil_scale": 1.2,
        "accregen_value": -6.0,
        "accdelay_value": 0.9,
        "accimpulse_value": 1.65,
        "accuracy_value": 7.0,
        "spread_value": 1.25,
        "firerate_value": 1.25,
        "damage_scale": 6.5
      },
      "VLA_StopGap": {
        "part_value": 1.0,
        "accdelay_value": 0.35,
        "accimpulse_value": 1.0,
        "accuracy_value": 5.0,
        "spread_value": 1.75,
        "firerate_value": 4.4,
        "damage_scale": 2.7
      },
      "BOR_Stray": {
        "part_value": 1.0,
        "projectilespershot_value": 3.0,
        "accimpulse_value": 0.6,
        "accuracy_value": 4.0,
        "spread_value": 1.5,
        "firerate_value": 2.25,
        "damage_scale": 3.0
      },
      "JAK_Truck": {
        "part_value": 1.0,
        "impact_force_value": 30000.0,
        "sway_scale": 0.85,
        "recoil_scale": 1.75,
        "accregen_value": -3.5,
        "accdelay_value": 0.8,
        "accimpulse_value": 5.0,
        "accuracy_value": 7.0,
        "spread_value": 0.75,
        "firerate_value": 1.0,
        "damage_scale": 15.0
      },
      "MAL_Asher": {
        "part_value": 1.0,
        "damageradius_value": 20.0,
        "statusdamage_scale": 2.0,
        "statuschance_scale": 0.0,
        "sway_scale": 0.5,
        "recoil_scale": 0.75,
        "accregen_value": -6.0,
        "accdelay_value": 0.8,
        "accimpulse_value": 0.65,
        "accuracy_value": 5.0,
        "spread_value": 1.5,
        "firerate_value": 6.6,
        "damage_scale": 5.0
      },
      "JAK_Ballista": {
        "part_value": 2.0,
        "accregen_value": -7.5,
        "accdelay_value": 1.25,
        "accimpulse_value": 2.3,
        "accuracy_value": 10.0,
        "spread_value": 0.95,
        "firerate_value": 0.8,
        "damage_scale": 10.0
      },
      "VLA_CrowdSourced": {
        "part_value": 1.0,
        "accdelay_value": 0.35,
        "accimpulse_value": 1.0,
        "accuracy_value": 5.0,
        "spread_value": 1.75,
        "firerate_value": 4.0,
        "damage_scale": 2.9
      }
    }
  },
  "Weapon_AIDamageScale": {
    "table_name": "Weapon_AIDamageScale",
    "rows": {
      "DAD_AR_Barrel_01": {
        "damage_scale": 0.85
      },
      "DAD_AR_Barrel_02": {
        "damage_scale": 0.85
      },
      "JAK_AR_Barrel_01": {
        "damage_scale": 0.85
      },
      "JAK_AR_Barrel_02": {
        "damage_scale": 0.85
      },
      "ORD_AR_Barrel_01": {
        "damage_scale": 0.85
      },
      "ORD_AR_Barrel_02": {
        "damage_scale": 0.85
      },
      "TED_AR_Barrel_01": {
        "damage_scale": 0.85
      },
      "TED_AR_Barrel_02": {
        "damage_scale": 0.85
      },
      "TOR_AR_Barrel_01": {
        "damage_scale": 0.85
      },
      "TOR_AR_Barrel_02": {
        "damage_scale": 0.85
      },
      "VLA_AR_Barrel_01": {
        "damage_scale": 0.85
      },
      "VLA_AR_Barrel_02": {
        "damage_scale": 0.85
      },
      "DAD_PS_Barrel_01": {
        "damage_scale": 0.85
      },
      "DAD_PS_Barrel_02": {
        "damage_scale": 0.85
      },
      "JAK_PS_Barrel_01": {
        "damage_scale": 0.85
      },
      "JAK_PS_Barrel_02": {
        "damage_scale": 0.85
      },
      "ORD_PS_Barrel_01": {
        "damage_scale": 0.85
      },
      "ORD_PS_Barrel_02": {
        "damage_scale": 0.85
      },
      "TED_PS_Barrel_01": {
        "damage_scale": 0.85
      },
      "TED_PS_Barrel_02": {
        "damage_scale": 0.85
      },
      "TOR_PS_Barrel_01": {
        "damage_scale": 0.85
      },
      "TOR_PS_Barrel_02": {
        "damage_scale": 0.85
      },
      "BOR_SG_Barrel_01": {
        "damage_scale": 0.85
      },
      "BOR_SG_Barrel_02": {
        "damage_scale": 0.85
      },
      "DAD_SG_Barrel_01": {
        "damage_scale": 0.85
      },
      "DAD_SG_Barrel_02": {
        "damage_scale": 0.85
      },
      "JAK_SG_Barrel_01": {
        "damage_scale": 0.85
      },
      "JAK_SG_Barrel_02": {
        "damage_scale": 0.85
      },
      "MAL_SG_Barrel_01": {
        "impact_force_scale": 0.1,
        "damage_scale": 0.85
      },
      "MAL_SG_Barrel_02": {
        "damage_scale": 0.85
      },
      "TED_SG_Barrel_01": {
        "damage_scale": 0.85
      },
      "TED_SG_Barrel_02": {
        "damage_scale": 0.85
      },
      "TOR_SG_Barrel_01": {
        "damage_scale": 0.85
      },
      "TOR_SG_Barrel_02": {
        "damage_scale": 0.85
      },
      "BOR_SM_Barrel_01": {
        "damage_scale": 0.85
      },
      "BOR_SM_Barrel_02": {
        "damage_scale": 0.85
      },
      "DAD_SM_Barrel_01": {
        "damage_scale": 0.85
      },
      "DAD_SM_Barrel_02": {
        "damage_scale": 0.85
      },
      "MAL_SM_Barrel_01": {
        "damage_scale": 0.85
      },
      "MAL_SM_Barrel_02": {
        "damage_scale": 0.85
      },
      "VLA_SM_Barrel_01": {
        "damage_scale": 0.85
      },
      "VLA_SM_Barrel_02": {
        "damage_scale": 0.85
      },
      "BOR_SR_Barrel_01": {
        "damage_scale": 0.85
      },
      "BOR_SR_Barrel_02": {
        "damage_scale": 0.85
      },
      "JAK_SR_Barrel_01": {
        "damage_scale": 0.85
      },
      "JAK_SR_Barrel_02": {
        "damage_scale": 0.85
      },
      "MAL_SR_Barrel_01": {
        "damage_scale": 0.85
      },
      "MAL_SR_Barrel_02": {
        "impact_force_scale": 0.1,
        "damage_scale": 0.85
      },
      "ORD_SR_Barrel_01": {
        "damage_scale": 0.85
      },
      "ORD_SR_Barrel_02": {
        "damage_scale": 0.85
      },
      "VLA_SR_Barrel_01": {
        "damage_scale": 0.85
      },
      "VLA_SR_Barrel_02": {
        "damage_scale": 0.85
      },
      "BOR_HW_Barrel_01": {
        "damage_scale": 0.85
      },
      "BOR_HW_Barrel_02": {
        "damage_scale": 0.85
      },
      "MAL_HW_Barrel_01": {
        "damage_scale": 0.85
      },
      "MAL_HW_Barrel_02": {
        "damage_scale": 0.85
      },
      "TOR_HW_Barrel_01": {
        "damage_scale": 0.85
      },
      "TOR_HW_Barrel_02": {
        "damage_scale": 0.85
      },
      "VLA_HW_Barrel_01": {
        "impact_force_scale": 0.5,
        "damage_scale": 0.85
      },
      "VLA_HW_Barrel_02": {
        "impact_force_scale": 0.25,
        "damage_scale": 0.85
      }
    }
  },
  "Weapon_AR_Barrel_Init": {
    "table_name": "Weapon_AR_Barrel_Init",
    "rows": {
      "DAD_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "sway_scale": 1.4,
        "accimpulse_value": 0.32,
        "accuracy_value": 4.3,
        "spread_value": 2.55,
        "firerate_value": 6.75,
        "damage_scale": 1.28
      },
      "DAD_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "accimpulse_value": 0.22,
        "accuracy_value": 3.2,
        "spread_value": 1.8,
        "firerate_value": 5.5,
        "damage_scale": 1.5
      },
      "JAK_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "recoil_scale": 0.75,
        "accdelay_value": 0.25,
        "accimpulse_value": 0.7,
        "accuracy_value": 6.0,
        "spread_value": 1.8,
        "firerate_value": 6.5,
        "damage_scale": 2.9
      },
      "JAK_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "recoil_scale": 1.2,
        "accregen_value": -10.0,
        "accdelay_value": 0.2,
        "accimpulse_value": 1.1,
        "accuracy_value": 5.0,
        "spread_value": 1.05,
        "firerate_value": 4.75,
        "damage_scale": 3.4
      },
      "VLA_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "sway_scale": 1.2,
        "accregen_value": -4.0,
        "accimpulse_value": 0.35,
        "accuracy_value": 3.1,
        "spread_value": 2.4,
        "firerate_value": 11.5,
        "damage_scale": 0.975
      },
      "VLA_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "accregen_value": -6.0,
        "accimpulse_value": 0.275,
        "accuracy_value": 3.65,
        "spread_value": 2.1,
        "firerate_value": 9.915,
        "damage_scale": 1.05
      },
      "TOR_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "damageradius_value": 135.0,
        "accimpulse_value": 0.5,
        "accuracy_value": 3.25,
        "spread_value": 2.5,
        "firerate_value": 3.5,
        "damage_scale": 2.6
      },
      "TOR_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "damageradius_value": 135.0,
        "accimpulse_value": 0.45,
        "accuracy_value": 3.75,
        "spread_value": 2.5,
        "firerate_value": 2.5,
        "damage_scale": 3.4
      },
      "TED_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "accregen_value": -9.0,
        "accdelay_value": 0.4,
        "accimpulse_value": 0.35,
        "accuracy_value": 5.2,
        "spread_value": 3.5,
        "firerate_value": 4.5,
        "damage_scale": 2.0
      },
      "TED_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "accregen_value": -8.5,
        "accdelay_value": 0.4,
        "accimpulse_value": 0.3,
        "accuracy_value": 4.25,
        "spread_value": 2.55,
        "firerate_value": 3.65,
        "damage_scale": 2.35
      },
      "ORD_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 16000.0,
        "recoil_scale": 0.8,
        "accregen_value": -6.0,
        "accuracy_value": 1.7,
        "spread_value": 1.2,
        "firerate_value": 5.5,
        "damage_scale": 2.5
      },
      "ORD_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 16000.0,
        "accregen_value": -6.0,
        "accimpulse_value": 0.35,
        "accuracy_value": 2.0,
        "spread_value": 1.0,
        "firerate_value": 6.5,
        "damage_scale": 2.2
      }
    }
  },
  "Weapon_AR_Magazine_Init": {
    "table_name": "Weapon_AR_Magazine_Init",
    "rows": {
      "DAD_Mag_01": {
        "heatimpulse_value": 0.04,
        "reloadtime_value": 2.1,
        "maxloadedammo_value": 28.0
      },
      "DAD_Mag_02": {
        "heatimpulse_value": 0.0265,
        "reloadtime_value": 2.6,
        "maxloadedammo_value": 36.0
      },
      "DAD_Mag_03": {
        "heatimpulse_value": 0.055,
        "sway_scale": 1.15,
        "recoil_scale": 1.3,
        "firerate_scale": 0.85,
        "damage_scale": 1.3,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 20.0
      },
      "DAD_Mag_04": {
        "heatimpulse_value": 0.02,
        "sway_scale": 1.25,
        "recoil_scale": 1.1,
        "spread_scale": 1.4,
        "accuracy_scale": 1.25,
        "damage_scale": 1.1,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 4.3
      },
      "DAD_Mag_05": {
        "heatimpulse_value": 0.03,
        "recoil_scale": 1.05,
        "spread_scale": 0.95,
        "accuracy_scale": 0.9,
        "firerate_scale": 1.1,
        "damage_scale": 1.05,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.0,
        "maxloadedammo_value": 44.0
      },
      "JAK_Mag_01": {
        "heatimpulse_value": 0.055,
        "damage_scale": 0.9,
        "reloadtime_value": 2.5,
        "maxloadedammo_value": 14.0
      },
      "JAK_Mag_02": {
        "heatimpulse_value": 0.045,
        "firerate_scale": 1.1,
        "damage_scale": 0.85,
        "reloadtime_value": 2.7,
        "maxloadedammo_value": 18.0
      },
      "JAK_Mag_03": {
        "heatimpulse_value": 0.083,
        "spread_scale": 1.1,
        "accuracy_scale": 1.1,
        "firerate_scale": 0.8,
        "damage_scale": 0.85,
        "reloadtime_value": 2.6,
        "maxloadedammo_value": 16.0
      },
      "JAK_Mag_04": {
        "heatimpulse_value": 0.06,
        "recoil_scale": 1.2,
        "spread_scale": 1.4,
        "damage_scale": 0.8375,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 4.0
      },
      "JAK_Mag_05": {
        "heatimpulse_value": 0.0625,
        "firerate_scale": 1.25,
        "damage_scale": 0.6,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 24.0
      },
      "VLA_Mag_01": {
        "heatimpulse_value": 0.03,
        "reloadtime_value": 2.9,
        "maxloadedammo_value": 40.0
      },
      "VLA_Mag_02": {
        "heatimpulse_value": 0.02,
        "recoil_scale": 1.05,
        "reloadtime_value": 3.4,
        "maxloadedammo_value": 50.0
      },
      "VLA_Mag_03": {
        "heatimpulse_value": 0.038,
        "recoil_scale": 1.2,
        "spread_scale": 0.9,
        "firerate_scale": 0.8,
        "damage_scale": 1.3,
        "reloadtime_value": 2.8,
        "maxloadedammo_value": 30.0
      },
      "VLA_Mag_04": {
        "heatimpulse_value": 0.0165,
        "sway_scale": 1.2,
        "recoil_scale": 1.3,
        "spread_scale": 1.4,
        "damage_scale": 0.85,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 5.5
      },
      "VLA_Mag_05": {
        "heatimpulse_value": 0.025,
        "firerate_scale": 1.25,
        "damage_scale": 0.95,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.7,
        "maxloadedammo_value": 60.0
      },
      "TOR_Mag_01": {
        "heatimpulse_value": 0.125,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 14.0
      },
      "TOR_Mag_02": {
        "heatimpulse_value": 0.07,
        "reloadtime_value": 2.8,
        "maxloadedammo_value": 20.0
      },
      "TOR_Mag_04": {
        "heatimpulse_value": 0.04,
        "recoil_scale": 1.2,
        "spread_scale": 1.4,
        "damage_scale": 1.05,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 4.0
      },
      "TOR_Mag_05": {
        "heatimpulse_value": 0.06,
        "firerate_scale": 1.2,
        "damage_scale": 0.95,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 24.0
      },
      "TED_Mag_01": {
        "heatimpulse_value": 0.03,
        "reloadtime_value": 2.2,
        "maxloadedammo_value": 20.0
      },
      "TED_Mag_02": {
        "heatimpulse_value": 0.02,
        "reloadtime_value": 2.6,
        "maxloadedammo_value": 24.0
      },
      "TED_Mag_03": {
        "heatimpulse_value": 0.05,
        "firerate_scale": 0.9,
        "damage_scale": 1.34,
        "reloadtime_value": 2.8,
        "maxloadedammo_value": 16.0
      },
      "TED_Mag_04": {
        "heatimpulse_value": 0.035,
        "recoil_scale": 1.2,
        "spread_scale": 1.4,
        "damage_scale": 1.05,
        "reloadtime_value": 3.6
      },
      "TED_Mag_05": {
        "heatimpulse_value": 0.02,
        "firerate_scale": 1.2,
        "damage_scale": 1.01,
        "reloadtime_value": 2.8,
        "maxloadedammo_value": 30.0
      },
      "ORD_Mag_01": {
        "heatimpulse_value": 0.15,
        "reloadtime_value": 1.9,
        "maxloadedammo_value": 18.0
      },
      "ORD_Mag_02": {
        "heatimpulse_value": 0.12,
        "damage_scale": 0.95,
        "reloadtime_value": 2.3,
        "maxloadedammo_value": 24.0
      },
      "ORD_Mag_03": {
        "heatimpulse_value": 0.175,
        "firerate_scale": 0.825,
        "damage_scale": 1.35,
        "reloadtime_value": 2.1,
        "maxloadedammo_value": 15.0
      },
      "ORD_Mag_04": {
        "heatimpulse_value": 0.03,
        "recoil_scale": 1.2,
        "spread_scale": 1.4,
        "damage_scale": 1.03,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.7
      },
      "ORD_Mag_05": {
        "heatimpulse_value": 0.135,
        "firerate_scale": 1.2,
        "damage_scale": 0.975,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.3,
        "maxloadedammo_value": 30.0
      }
    }
  },
  "Weapon_AR_Underbarrel_Init": {
    "table_name": "Weapon_AR_Underbarrel_Init",
    "rows": {
      "DAD_Grenade": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.25,
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2,
        "damageradius_value": 400.0,
        "accdelay_value": 1.0,
        "accimpulse_value": 1.0,
        "accuracy_value": 3.0,
        "ammoregen_value": 3.0,
        "ammo_value": 3.0,
        "spread_value": 1.0,
        "firerate_value": 1.5,
        "damage_value": 110.0
      },
      "DAD_Shotgun": {
        "impactforce_value": 3750.0,
        "projectilespershot_value": 8.0,
        "heatimpulse_value": 0.15,
        "accdelay_value": 1.0,
        "accimpulse_value": 0.75,
        "accuracy_value": 3.0,
        "ammoregen_value": 6.0,
        "ammo_value": 6.0,
        "spread_value": 8.0,
        "firerate_value": 1.75,
        "damage_value": 24.0
      },
      "DAD_Microrockets": {
        "impactforce_value": 30000.0,
        "heatimpulse_value": 0.05,
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2,
        "sway_scale": 1.35,
        "damageradius_value": 200.0,
        "accimpulse_value": 0.6,
        "accuracy_value": 5.0,
        "ammodelay_value": 24.0,
        "ammoregen_value": 15.0,
        "ammo_value": 15.0,
        "spread_value": 5.0,
        "firerate_value": 7.5,
        "damage_value": 24.0
      },
      "DAD_Atlas": {
        "projectilespershot_value": 5.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.3,
        "modeswitch_scale": 1.4,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "DAD_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.3,
        "modeswitch_scale": 1.4,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "DAD_AmmoSwitcher": {
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125
      },
      "VLA_Grenade": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.25,
        "modeswitch_scale": 1.1,
        "damageradius_value": 300.0,
        "accimpulse_value": 1.0,
        "accuracy_value": 6.0,
        "ammoregen_value": 3.0,
        "ammo_value": 3.0,
        "spread_value": 4.0,
        "firerate_value": 1.25,
        "damage_value": 110.0
      },
      "VLA_Shotgun": {
        "impactforce_value": 5000.0,
        "projectilespershot_value": 6.0,
        "heatimpulse_value": 0.1,
        "modereturn_scale": 0.875,
        "accimpulse_value": 0.35,
        "accuracy_value": 4.0,
        "ammodelay_value": 14.0,
        "ammoregen_value": 4.0,
        "ammo_value": 8.0,
        "spread_value": 6.0,
        "firerate_value": 4.5,
        "damage_value": 12.0
      },
      "VLA_Bipod": {
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.275,
        "sway_scale": 0.25,
        "recoil_scale": 0.25,
        "accimpulse_value": 0.25,
        "accuracy_value": 0.75,
        "spread_value": 0.75
      },
      "VLA_SecondBarrel_Scale": {
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2,
        "sway_scale": 1.2,
        "accuracy_value": 2.0,
        "spread_value": 2.0,
        "firerate_value": 1.5
      },
      "VLA_Atlas": {
        "projectilespershot_value": 5.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "VLA_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "VLA_AmmoSwitcher": {
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125
      },
      "TOR_Grenade": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.5,
        "modereturn_scale": 1.25,
        "modeswitch_scale": 1.25,
        "damageradius_value": 250.0,
        "accdelay_value": 1.0,
        "accimpulse_value": 1.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 30.0,
        "spread_value": 1.0,
        "firerate_value": 1.5,
        "damage_value": 110.0
      },
      "TOR_Shotgun": {
        "impactforce_value": 5000.0,
        "projectilespershot_value": 6.0,
        "heatimpulse_value": 0.25,
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2,
        "damageradius_value": 150.0,
        "accdelay_value": 1.0,
        "accimpulse_value": 0.5,
        "accuracy_value": 3.0,
        "ammoregen_value": 3.0,
        "ammo_value": 3.0,
        "spread_value": 3.25,
        "firerate_value": 1.25,
        "damage_value": 32.0
      },
      "TOR_Airstrike": {
        "impactforce_value": 100000.0,
        "heatimpulse_value": 0.2,
        "damageradius_value": 600.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 60.0,
        "firerate_value": 1.0,
        "damage_value": 400.0
      },
      "TOR_Atlas": {
        "projectilespershot_value": 5.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.25,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "TOR_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.25,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "TOR_AmmoSwitcher": {
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5
      },
      "TOR_MalElement": {
        "modeswitch_scale": 1.25
      },
      "JAK_Flintlock": {
        "impactforce_value": 60000.0,
        "projectilespershot_value": 2.0,
        "heatimpulse_value": 0.3,
        "modereturn_scale": 1.25,
        "modeswitch_scale": 1.25,
        "damageradius_value": 10.0,
        "accimpulse_value": 0.5,
        "accuracy_value": 4.0,
        "ammodelay_value": 15.0,
        "spread_value": 2.5,
        "firerate_value": 1.0,
        "damage_value": 150.0
      },
      "JAK_Crank": {
        "heatimpulse_value": 0.04,
        "modereturn_scale": 0.7,
        "modeswitch_scale": 0.7,
        "sway_scale": 2.0,
        "recoil_scale": 0.4,
        "accdelay_value": 0.25,
        "accimpulse_value": 0.35,
        "accuracy_value": 6.0,
        "ammoregen_value": 24.0,
        "ammo_value": 24.0,
        "spread_value": 3.0,
        "firerate_value": 7.0,
        "damage_value": 22.0
      },
      "JAK_Shotgun": {
        "impactforce_value": 3333.3333,
        "projectilespershot_value": 9.0,
        "heatimpulse_value": 0.15,
        "modereturn_scale": 1.25,
        "modeswitch_scale": 1.25,
        "accuracy_value": 3.0,
        "ammodelay_value": 15.0,
        "ammoregen_value": 5.0,
        "ammo_value": 5.0,
        "spread_value": 7.0,
        "firerate_value": 1.65,
        "damage_value": 18.0
      },
      "JAK_Atlas": {
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "JAK_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "JAK_AmmoSwitcher": {
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125
      },
      "TED_BuffDrone": {
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "damageradius_value": 25.0,
        "accimpulse_value": 1.0,
        "accuracy_value": 5.0,
        "ammodelay_value": 30.0,
        "spread_value": 4.0,
        "firerate_value": 2.0,
        "damage_value": 10.0
      },
      "TED_ComboOrb": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.3,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "damageradius_value": 500.0,
        "accimpulse_value": 0.7,
        "accuracy_value": 3.0,
        "ammodelay_value": 24.0,
        "spread_value": 7.0,
        "firerate_value": 2.0,
        "damage_value": 150.0
      },
      "TED_Shotgun": {
        "impactforce_value": 5000.0,
        "projectilespershot_value": 6.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "accimpulse_value": 0.65,
        "accuracy_value": 3.5,
        "ammoregen_value": 4.0,
        "ammo_value": 4.0,
        "spread_value": 7.0,
        "firerate_value": 2.25,
        "damage_value": 20.0
      },
      "TED_Atlas": {
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "accuracy_value": 2.0,
        "spread_value": 4.0,
        "firerate_value": 2.0
      },
      "TED_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "damageradius_value": 350.0,
        "accuracy_value": 2.0,
        "spread_value": 4.0,
        "firerate_value": 2.0
      },
      "TED_AmmoSwitcher": {
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125
      },
      "ORD_Seeker": {
        "impactforce_value": 30000.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.25,
        "accimpulse_value": 0.7,
        "accuracy_value": 4.0,
        "ammodelay_value": 24.0,
        "ammo_value": 4.0,
        "spread_value": 4.0,
        "firerate_value": 2.0,
        "damage_value": 100.0
      },
      "ORD_DeathSphere": {
        "impactforce_value": 5000.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.25,
        "damageradius_value": 50.0,
        "accimpulse_value": 1.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 30.0,
        "spread_value": 3.0,
        "firerate_value": 2.0,
        "damage_value": 55.0
      },
      "ORD_KillDrone": {
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.25,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 40.0,
        "spread_value": 3.0,
        "firerate_value": 2.0,
        "damage_value": 26.0
      },
      "ORD_Atlas": {
        "projectilespershot_value": 5.0,
        "heatimpulse_value": 0.2,
        "accuracy_value": 2.0,
        "spread_value": 4.0,
        "firerate_value": 2.0
      },
      "ORD_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "damageradius_value": 350.0,
        "accuracy_value": 2.0,
        "spread_value": 3.0,
        "firerate_value": 2.0
      }
    }
  },
  "Weapon_OrderFiring": {
    "table_name": "Weapon_OrderFiring",
    "rows": {
      "PS_Barrel_01": {
        "loadedshotadditionalprojectile": 1.0,
        "loadedshotheatimpulsescale": 1.0,
        "loadedshotrecoilscale": 0.5,
        "loadedshotimpulsescale": 0.8,
        "loadedshotspreadscale": 0.15,
        "loadedshotdamageradiusscale": 0.25,
        "loadedshotdamagescale": -0.1,
        "maxloadedshots": 5.0,
        "chargetime": 0.245
      },
      "PS_Barrel_02": {
        "loadedshotadditionalprojectile": 1.0,
        "loadedshotheatimpulsescale": 1.0,
        "loadedshotrecoilscale": 0.5,
        "loadedshotimpulsescale": 1.0,
        "loadedshotdamageradiusscale": 0.25,
        "loadedshotdamagescale": -0.085,
        "maxloadedshots": 5.0,
        "chargetime": 0.295
      },
      "AR_Barrel_01": {
        "loadedshotadditionalprojectile": 1.0,
        "loadedshotheatimpulsescale": 0.0,
        "loadedshotrecoilscale": -0.125,
        "loadedshotimpulsescale": 0.0,
        "loadedshotspreadscale": 0.15,
        "loadedshotdamageradiusscale": 0.25,
        "loadedshotdamagescale": -0.1,
        "maxloadedshots": 5.0,
        "chargetime": 0.255
      },
      "AR_Barrel_02": {
        "loadedshotadditionalprojectile": 1.0,
        "loadedshotheatimpulsescale": 0.0,
        "loadedshotrecoilscale": -0.1,
        "loadedshotimpulsescale": 0.0,
        "loadedshotdamageradiusscale": 0.25,
        "loadedshotdamagescale": -0.085,
        "maxloadedshots": 5.0,
        "chargetime": 0.285
      },
      "SR_Barrel_01": {
        "loadedshotheatimpulsescale": 1.0,
        "loadedshotrecoilscale": 0.15,
        "loadedshotimpulsescale": 0.48,
        "loadedshotspreadscale": 0.0,
        "loadedshotdamageradiusscale": 0.25,
        "loadedshotdamagescale": 0.5,
        "maxloadedshots": 5.0,
        "chargetime": 0.305
      },
      "SR_Barrel_02": {
        "loadedshotheatimpulsescale": 1.0,
        "loadedshotrecoilscale": 0.2,
        "loadedshotimpulsescale": 0.48,
        "loadedshotspreadscale": 0.0,
        "loadedshotdamageradiusscale": 0.25,
        "loadedshotdamagescale": 0.575,
        "maxloadedshots": 5.0,
        "chargetime": 0.315
      },
      "AR_Underbarrel_01": {
        "loadedshotadditionalprojectile": 1.0,
        "loadedshotrecoilscale": -0.25,
        "loadedshotspreadscale": 0.0,
        "loadedshotdamagescale": 0.0,
        "maxloadedshots": 3.0,
        "chargetime": 0.5
      },
      "PS_UB_01_EnergyBurst": {
        "loadedshotheatimpulsescale": 0.0,
        "loadedshotrecoilscale": 0.0,
        "loadedshotimpulsescale": 0.0,
        "loadedshotspreadscale": 0.0,
        "loadedshotdamageradiusscale": 0.2,
        "loadedshotdamagescale": 0.0,
        "maxloadedshots": 1.0,
        "chargetime": 2.0
      },
      "PS_UB_02_GravWell": {
        "loadedshotspreadscale": 0.0,
        "loadedshotdamageradiusscale": 0.2,
        "maxloadedshots": 1.0
      },
      "PS_UB_03_ChargedRockets": {
        "loadedshotadditionalprojectile": 1.0,
        "loadedshotheatimpulsescale": 0.0,
        "loadedshotrecoilscale": 0.0,
        "loadedshotimpulsescale": 0.0,
        "loadedshotspreadscale": 0.0,
        "loadedshotdamagescale": 0.0,
        "maxloadedshots": 5.0,
        "chargetime": 0.3
      },
      "SR_UB_03_Railgun": {
        "loadedshotheatimpulsescale": 0.0,
        "loadedshotrecoilscale": 0.0,
        "loadedshotimpulsescale": 0.0,
        "loadedshotspreadscale": 0.0,
        "loadedshotdamagescale": 0.0,
        "maxloadedshots": 0.0
      }
    }
  },
  "weapon_part_weight_table": {
    "table_name": "weapon_part_weight_table",
    "rows": {
      "Body_Mod_Elemental": {
        "none": 0.25
      },
      "Barrel_Mod_Hyp": {
        "none": 0.375
      },
      "Barrel_Mod_Jak": {
        "none": 0.375
      },
      "Barrel_Mod_Ted": {
        "none": 0.0375
      },
      "Barrel_Mod_Ted_Combo": {
        "none": 0.0375
      },
      "Barrel_Mod_Ted_MIRV": {
        "none": 0.0375
      },
      "Barrel_Mod_Ted_Shooting": {
        "none": 0.0375
      },
      "Barrel_Mod_Ted_Multi": {
        "none": 0.075
      },
      "Mag_Torgue": {
        "none": 0.325
      },
      "Mag_COV": {
        "none": 0.325
      },
      "Mag_Borg": {
        "none": 0.325
      },
      "HypShield_Default": {
        "none": 3.0
      },
      "HypShield_Reflect": {
        "none": 1.0
      },
      "HypShield_Absorb": {
        "none": 1.0
      },
      "HypShield_Amp": {
        "none": 1.0
      },
      "Grip_Ted_Homing": {
        "none": 0.375
      },
      "Grip_Ted_Legs": {
        "none": 0.375
      },
      "Grip_Ted_Javelin": {
        "none": 0.375
      },
      "Grip_Hyp": {
        "none": 0.3
      },
      "Underbarrel_Default": {
        "none": 0.4
      },
      "Underbarrel_Atlas": {
        "none": 0.4
      },
      "Underbarrel_Dad": {
        "none": 0.4
      },
      "Underbarrel_Mal": {
        "none": 0.4
      }
    }
  },
  "Weapon_PS_Barrel_Init": {
    "table_name": "Weapon_PS_Barrel_Init",
    "rows": {
      "JAK_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "recoil_scale": 0.8,
        "accdelay_value": 0.28,
        "accimpulse_value": 0.6,
        "accuracy_value": 2.45,
        "spread_value": 3.2,
        "firerate_value": 9.0,
        "damage_scale": 4.0
      },
      "JAK_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "accregen_value": -10.0,
        "accdelay_value": 0.45,
        "accimpulse_value": 0.8,
        "accuracy_value": 4.0,
        "spread_value": 1.45,
        "firerate_value": 7.5,
        "damage_scale": 4.2
      },
      "ORD_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "recoil_scale": 1.2,
        "accregen_value": -6.0,
        "accimpulse_value": 0.65,
        "accuracy_value": 2.0,
        "spread_value": 2.1,
        "firerate_value": 8.0,
        "damage_scale": 1.85
      },
      "ORD_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "accregen_value": -6.5,
        "accimpulse_value": 0.8,
        "accuracy_value": 2.5,
        "spread_value": 1.7,
        "firerate_value": 6.5,
        "damage_scale": 2.0
      },
      "TED_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "accregen_value": -8.5,
        "accdelay_value": 0.35,
        "accimpulse_value": 0.35,
        "accuracy_value": 3.2,
        "spread_value": 6.2,
        "firerate_value": 6.0,
        "damage_scale": 1.55
      },
      "TED_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "accregen_value": -8.25,
        "accdelay_value": 0.4,
        "accimpulse_value": 0.3,
        "accuracy_value": 2.45,
        "spread_value": 4.2,
        "firerate_value": 4.8,
        "damage_scale": 1.8
      },
      "DAD_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "sway_scale": 1.15,
        "accregen_value": -5.0,
        "accdelay_value": 0.4,
        "accimpulse_value": 0.225,
        "accuracy_value": 2.0,
        "spread_value": 3.15,
        "firerate_value": 18.0,
        "damage_scale": 1.55
      },
      "DAD_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "recoil_scale": 1.5,
        "accregen_value": -6.0,
        "accdelay_value": 0.45,
        "accimpulse_value": 0.175,
        "accuracy_value": 2.0,
        "spread_value": 1.8,
        "firerate_value": 14.0,
        "damage_scale": 1.6
      },
      "TOR_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 12500.0,
        "damageradius_value": 135.0,
        "accdelay_value": 0.6,
        "accimpulse_value": 1.25,
        "accuracy_value": 3.0,
        "spread_value": 2.5,
        "firerate_value": 2.5,
        "damage_scale": 4.0
      },
      "TOR_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 12500.0,
        "damageradius_value": 135.0,
        "accdelay_value": 0.6,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.5,
        "spread_value": 1.8,
        "firerate_value": 1.75,
        "damage_scale": 5.0
      }
    }
  },
  "Weapon_PS_Magazine_Init": {
    "table_name": "Weapon_PS_Magazine_Init",
    "rows": {
      "JAK_Mag_01": {
        "thrownreloadcompletepercent": 0.325,
        "heatimpulse_value": 0.1,
        "reloadtime_value": 2.35,
        "maxloadedammo_value": 4.0
      },
      "JAK_Mag_02": {
        "thrownreloadcompletepercent": 0.325,
        "heatimpulse_value": 0.08,
        "damage_scale": 0.7,
        "reloadtime_value": 2.25,
        "maxloadedammo_value": 6.0
      },
      "JAK_Mag_03": {
        "thrownreloadcompletepercent": 0.325,
        "heatimpulse_value": 0.06,
        "recoil_scale": 1.15,
        "spread_scale": 1.1,
        "accuracy_scale": 1.1,
        "firerate_scale": 0.8,
        "damage_scale": 0.825,
        "reloadtime_value": 2.85,
        "maxloadedammo_value": 8.0
      },
      "JAK_Mag_04": {
        "thrownreloadcompletepercent": 0.675,
        "heatimpulse_value": 0.2,
        "sway_scale": 1.1,
        "recoil_scale": 1.1,
        "spread_scale": 1.4,
        "accuracy_scale": 1.2,
        "damage_scale": 0.675,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.2
      },
      "JAK_Mag_05": {
        "thrownreloadcompletepercent": 0.5,
        "heatimpulse_value": 0.08,
        "recoil_scale": 0.9,
        "firerate_scale": 0.8,
        "damage_scale": 0.875,
        "reloadtime_value": 2.25,
        "maxloadedammo_value": 8.0
      },
      "ORD_Mag_01": {
        "thrownreloadcompletepercent": 0.325,
        "heatimpulse_value": 0.085,
        "reloadtime_value": 1.9,
        "maxloadedammo_value": 15.0
      },
      "ORD_Mag_02": {
        "thrownreloadcompletepercent": 0.325,
        "heatimpulse_value": 0.0725,
        "damage_scale": 0.9875,
        "reloadtime_value": 2.8,
        "maxloadedammo_value": 18.0
      },
      "ORD_Mag_03": {
        "thrownreloadcompletepercent": 0.325,
        "heatimpulse_value": 0.1,
        "recoil_scale": 1.3,
        "spread_scale": 0.9,
        "accuracy_scale": 0.9,
        "firerate_scale": 0.825,
        "damage_scale": 1.25,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 12.0
      },
      "ORD_Mag_04": {
        "thrownreloadcompletepercent": 0.675,
        "heatimpulse_value": 0.05,
        "sway_scale": 1.15,
        "recoil_scale": 1.3,
        "spread_scale": 1.4,
        "damage_scale": 0.9375,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.9
      },
      "ORD_Mag_05": {
        "thrownreloadcompletepercent": 0.5,
        "heatimpulse_value": 0.08,
        "recoil_scale": 0.8,
        "accuracy_scale": 0.75,
        "firerate_scale": 1.225,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.3,
        "maxloadedammo_value": 24.0
      },
      "TED_Mag_01": {
        "heatimpulse_value": 0.06,
        "reloadtime_value": 1.4,
        "maxloadedammo_value": 14.0
      },
      "TED_Mag_02": {
        "heatimpulse_value": 0.045,
        "reloadtime_value": 1.8,
        "maxloadedammo_value": 18.0
      },
      "TED_Mag_03": {
        "heatimpulse_value": 0.07,
        "recoil_scale": 1.2,
        "spread_scale": 0.9,
        "firerate_scale": 0.8,
        "damage_scale": 1.3,
        "reloadtime_value": 1.6,
        "maxloadedammo_value": 12.0
      },
      "TED_Mag_04": {
        "heatimpulse_value": 0.04,
        "sway_scale": 1.2,
        "recoil_scale": 1.2,
        "spread_scale": 1.4,
        "damage_scale": 1.1,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.0
      },
      "TED_Mag_05": {
        "heatimpulse_value": 0.055,
        "firerate_scale": 1.3,
        "damage_scale": 1.1,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.5,
        "maxloadedammo_value": 24.0
      },
      "DAD_Mag_01": {
        "thrownreloadcompletepercent": 0.2825,
        "heatimpulse_value": 0.065,
        "damage_scale": 1.075,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 16.0
      },
      "DAD_Mag_02": {
        "thrownreloadcompletepercent": 0.2825,
        "heatimpulse_value": 0.045,
        "damage_scale": 1.125,
        "reloadtime_value": 2.7,
        "maxloadedammo_value": 20.0
      },
      "DAD_Mag_03": {
        "thrownreloadcompletepercent": 0.2825,
        "heatimpulse_value": 0.055,
        "recoil_scale": 1.3,
        "spread_scale": 0.8,
        "accuracy_scale": 0.9,
        "firerate_scale": 0.825,
        "damage_scale": 1.6,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 12.0
      },
      "DAD_Mag_04": {
        "thrownreloadcompletepercent": 0.675,
        "heatimpulse_value": 0.04,
        "sway_scale": 1.15,
        "recoil_scale": 1.4,
        "spread_scale": 1.4,
        "damage_scale": 1.095,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.5
      },
      "DAD_Mag_05_B01": {
        "thrownreloadcompletepercent": 0.5,
        "heatimpulse_value": 0.0385,
        "firerate_scale": 0.425,
        "damage_scale": 0.9375,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 1.75,
        "maxloadedammo_value": 28.0
      },
      "DAD_Mag_05_B02": {
        "thrownreloadcompletepercent": 0.5,
        "heatimpulse_value": 0.0385,
        "firerate_scale": 0.525,
        "damage_scale": 0.9375,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 1.75,
        "maxloadedammo_value": 28.0
      },
      "TOR_Mag_01": {
        "heatimpulse_value": 0.165,
        "reloadtime_value": 1.75,
        "maxloadedammo_value": 6.0
      },
      "TOR_Mag_02": {
        "heatimpulse_value": 0.12,
        "reloadtime_value": 2.25,
        "maxloadedammo_value": 8.0
      },
      "TOR_Mag_04": {
        "heatimpulse_value": 0.125,
        "spread_scale": 1.4,
        "accuracy_scale": 0.9,
        "damage_scale": 1.066,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.5
      },
      "TOR_Mag_05": {
        "heatimpulse_value": 0.038,
        "sway_scale": 1.2,
        "recoil_scale": 1.1,
        "spread_scale": 1.2,
        "accuracy_scale": 1.2,
        "firerate_scale": 1.25,
        "damage_scale": 1.08,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.75,
        "maxloadedammo_value": 10.0
      }
    }
  },
  "Weapon_PS_Underbarrel_Init": {
    "table_name": "Weapon_PS_Underbarrel_Init",
    "rows": {
      "JAK_Rockets": {
        "impactforce_value": 30000.0,
        "heatimpulse_value": 0.5,
        "damageradius_value": 150.0,
        "accdelay_value": 1.0,
        "accimpulse_value": 0.5,
        "accuracy_value": 5.0,
        "ammodelay_value": 10.0,
        "ammo_value": 5.0,
        "spread_value": 3.0,
        "firerate_value": 6.0,
        "damage_value": 45.0
      },
      "JAK_KnifeLauncher": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.3,
        "critdamage_add": 0.65,
        "accimpulse_value": 1.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 30.0,
        "spread_value": 1.25,
        "firerate_value": 1.0,
        "damage_value": 250.0
      },
      "JAK_Vial": {
        "heatimpulse_value": 0.15,
        "damageradius_value": 500.0,
        "accdelay_value": 0.85,
        "accimpulse_value": 0.65,
        "accuracy_value": 3.0,
        "ammo_value": 4.0,
        "spread_value": 3.0,
        "firerate_value": 1.75,
        "damage_value": 40.0
      },
      "JAK_Atlas": {
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.2,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 3.0,
        "firerate_value": 4.0
      },
      "JAK_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "JAK_AmmoSwitcher": {
        "modeswitch_scale": 1.25
      },
      "TED_Drone": {
        "heatimpulse_value": 0.35,
        "damageradius_value": 300.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 30.0,
        "spread_value": 2.75,
        "firerate_value": 2.0,
        "damage_value": 45.0
      },
      "TED_Rockets": {
        "impactforce_value": 30000.0,
        "heatimpulse_value": 0.15,
        "damageradius_value": 150.0,
        "accimpulse_value": 0.35,
        "accuracy_value": 2.5,
        "ammodelay_value": 24.0,
        "ammo_value": 6.0,
        "spread_value": 5.0,
        "firerate_value": 3.0,
        "damage_value": 60.0
      },
      "TED_Shotgun": {
        "impactforce_value": 7500.0,
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.25,
        "accimpulse_value": 0.75,
        "accuracy_value": 3.0,
        "ammodelay_value": 12.0,
        "ammoregen_value": 3.0,
        "ammo_value": 3.0,
        "spread_value": 8.0,
        "firerate_value": 5.0,
        "damage_value": 20.0
      },
      "TED_Atlas": {
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.1,
        "modeswitch_scale": 1.1,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "TED_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.1,
        "modeswitch_scale": 1.1,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "ORD_EnergyBurst": {
        "impactforce_value": 90000.0,
        "heatimpulse_value": 0.4,
        "damageradius_value": 500.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 24.0,
        "spread_value": 2.0,
        "firerate_value": 2.5,
        "damage_value": 280.0
      },
      "ORD_GravityWell": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.4,
        "damageradius_value": 350.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 40.0,
        "spread_value": 2.0,
        "firerate_value": 1.0,
        "damage_value": 20.0
      },
      "ORD_Rockets": {
        "heatimpulse_value": 0.15,
        "damageradius_value": 100.0,
        "accimpulse_value": 0.3,
        "accuracy_value": 2.0,
        "ammo_value": 6.0,
        "spread_value": 7.0,
        "firerate_value": 8.0,
        "damage_value": 30.0
      },
      "ORD_Atlas": {
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.2,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "ORD_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "ORD_AmmoSwitcher": {
        "modereturn_scale": 1.3,
        "modeswitch_scale": 1.3
      },
      "DAD_Taser": {
        "heatimpulse_value": 0.3,
        "damageradius_value": 50.0,
        "accuracy_value": 5.0,
        "spread_value": 5.0,
        "firerate_value": 1.0,
        "damage_value": 16.0
      },
      "DAD_KnifeLauncher": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.1,
        "modereturn_scale": 1.3,
        "modeswitch_scale": 1.6,
        "sway_scale": 0.5,
        "accuracy_value": 5.0,
        "ammodelay_value": 30.0,
        "ammoregen_value": 4.0,
        "ammo_value": 8.0,
        "spread_value": 2.0,
        "firerate_value": 2.0,
        "damage_value": 80.0
      },
      "DAD_Semtex": {
        "impactforce_value": 60000.0,
        "projectilespershot_value": 3.0,
        "heatimpulse_value": 0.25,
        "modereturn_scale": 1.25,
        "modeswitch_scale": 1.25,
        "damageradius_value": 350.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 40.0,
        "ammo_value": 3.0,
        "spread_value": 6.0,
        "firerate_value": 1.0,
        "damage_value": 50.0
      },
      "DAD_Atlas": {
        "projectilespershot_value": 3.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.75,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "DAD_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.75,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "DAD_AmmoSwitcher": {
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2
      },
      "DAD_MalElement": {
        "modereturn_scale": 0.9,
        "modeswitch_scale": 0.9
      },
      "TOR_Missiles": {
        "impactforce_value": 30000.0,
        "heatimpulse_value": 0.4,
        "damageradius_value": 350.0,
        "accdelay_value": 0.85,
        "accimpulse_value": 0.35,
        "accuracy_value": 5.0,
        "ammodelay_value": 30.0,
        "ammoregen_value": 2.0,
        "ammo_value": 2.0,
        "spread_value": 3.0,
        "firerate_value": 10.0,
        "damage_value": 125.0
      },
      "TOR_Exhaust": {
        "impactforce_value": 100000.0,
        "heatimpulse_value": 0.3,
        "modereturn_scale": 0.8,
        "modeswitch_scale": 0.9,
        "damageradius_value": 500.0,
        "accdelay_value": 1.0,
        "accimpulse_value": 0.5,
        "accuracy_value": 5.0,
        "ammodelay_value": 24.0,
        "spread_value": 3.0,
        "firerate_value": 1.425,
        "damage_value": 115.0
      },
      "TOR_Cleaver": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.3,
        "critdamage_add": 0.65,
        "damageradius_value": 50.0,
        "accimpulse_value": 1.0,
        "accuracy_value": 3.0,
        "spread_value": 0.5,
        "firerate_value": 3.5,
        "damage_value": 250.0
      },
      "TOR_Atlas": {
        "projectilespershot_value": 5.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 0.8,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 3.0,
        "firerate_value": 4.0
      },
      "TOR_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 0.8,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "TOR_AmmoSwitcher": {
        "modereturn_scale": 0.8
      }
    }
  },
  "Weapon_SG_Barrel_Init": {
    "table_name": "Weapon_SG_Barrel_Init",
    "rows": {
      "JAK_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 5000.0,
        "projectilespershot_value": 6.0,
        "accdelay_value": 0.75,
        "accimpulse_value": 1.3,
        "accuracy_value": 4.5,
        "spread_value": 4.5,
        "firerate_value": 1.5,
        "damage_scale": 1.475
      },
      "JAK_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 3000.0,
        "projectilespershot_value": 10.0,
        "recoil_scale": 0.85,
        "accregen_value": -5.0,
        "accdelay_value": 0.9,
        "accimpulse_value": 1.7,
        "accuracy_value": 5.75,
        "spread_value": 8.75,
        "firerate_value": 1.3,
        "damage_scale": 1.5
      },
      "MAL_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 30000.0,
        "damageradius_value": 150.0,
        "statusdamage_scale": 1.5,
        "accregen_value": -4.0,
        "accdelay_value": 1.25,
        "accimpulse_value": 0.8,
        "accuracy_value": 3.5,
        "spread_value": 4.0,
        "firerate_value": 0.8,
        "damage_scale": 9.2
      },
      "MAL_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 15000.0,
        "projectilespershot_value": 2.0,
        "damageradius_value": 35.0,
        "statusdamage_scale": 1.5,
        "sway_scale": 0.9,
        "accdelay_value": 0.85,
        "accimpulse_value": 1.4,
        "accuracy_value": 4.0,
        "spread_value": 4.0,
        "firerate_value": 1.1,
        "damage_scale": 4.8
      },
      "TED_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 3750.0,
        "projectilespershot_value": 8.0,
        "accdelay_value": 0.75,
        "accimpulse_value": 1.0,
        "accuracy_value": 5.0,
        "spread_value": 7.0,
        "firerate_value": 1.25,
        "damage_scale": 0.75
      },
      "TED_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 3000.0,
        "projectilespershot_value": 10.0,
        "accdelay_value": 0.7,
        "accimpulse_value": 1.2,
        "accuracy_value": 6.0,
        "spread_value": 8.0,
        "firerate_value": 1.5,
        "damage_scale": 0.525
      },
      "TOR_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 10000.0,
        "projectilespershot_value": 4.0,
        "damageradius_value": 135.0,
        "accdelay_value": 0.9,
        "accimpulse_value": 0.9,
        "accuracy_value": 5.0,
        "spread_value": 6.0,
        "firerate_value": 1.2,
        "damage_scale": 2.6625
      },
      "TOR_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 7500.0,
        "projectilespershot_value": 4.0,
        "damageradius_value": 135.0,
        "accdelay_value": 1.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 6.0,
        "spread_value": 5.0,
        "firerate_value": 0.95,
        "damage_scale": 3.0
      },
      "BOR_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 7500.0,
        "projectilespershot_value": 4.0,
        "damageradius_value": 50.0,
        "accregen_value": -6.0,
        "accimpulse_value": 0.5,
        "accuracy_value": 4.0,
        "spread_value": 7.0,
        "firerate_value": 4.5,
        "damage_scale": 0.675
      },
      "BOR_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 5000.0,
        "projectilespershot_value": 6.0,
        "damageradius_value": 75.0,
        "recoil_scale": 1.2,
        "accregen_value": -7.0,
        "accdelay_value": 0.7,
        "accimpulse_value": 0.7,
        "accuracy_value": 4.0,
        "spread_value": 5.5,
        "firerate_value": 3.0,
        "damage_scale": 0.5625
      },
      "DAD_Barrel_01": {
        "part_value": 1.0,
        "impact_force_value": 5000.0,
        "projectilespershot_value": 6.0,
        "sway_scale": 1.2,
        "accimpulse_value": 0.75,
        "accuracy_value": 5.0,
        "spread_value": 8.5,
        "firerate_value": 4.2,
        "damage_scale": 0.475
      },
      "DAD_Barrel_02": {
        "part_value": 2.0,
        "impact_force_value": 7500.0,
        "projectilespershot_value": 4.0,
        "accimpulse_value": 0.6,
        "accuracy_value": 4.25,
        "spread_value": 6.5,
        "firerate_value": 3.5,
        "damage_scale": 0.775
      }
    }
  },
  "Weapon_SG_Magazine_Init": {
    "table_name": "Weapon_SG_Magazine_Init",
    "rows": {
      "JAK_Mag_01_B01": {
        "heatimpulse_value": 0.2,
        "damage_scale": 1.5,
        "reloadtime_value": 1.7,
        "maxloadedammo_value": 1.0
      },
      "JAK_Mag_01_B02": {
        "heatimpulse_value": 0.2,
        "reloadtime_value": 1.7,
        "maxloadedammo_value": 2.0
      },
      "JAK_Mag_02": {
        "heatimpulse_value": 0.16,
        "damage_scale": 0.9,
        "reloadtime_value": 2.15,
        "maxloadedammo_value": 6.0
      },
      "JAK_Mag_02_B02": {
        "heatimpulse_value": 0.16,
        "damage_scale": 0.9,
        "reloadtime_value": 4.3,
        "maxloadedammo_value": 6.0
      },
      "JAK_Mag_03": {
        "heatimpulse_value": 0.125,
        "recoil_scale": 1.25,
        "spread_scale": 0.9,
        "accuracy_scale": 0.9,
        "firerate_scale": 0.65,
        "damage_scale": 0.9,
        "reloadtime_value": 2.3,
        "maxloadedammo_value": 12.0
      },
      "JAK_Mag_04": {
        "heatimpulse_value": 0.17,
        "sway_scale": 1.2,
        "recoil_scale": 1.2,
        "spread_scale": 1.2,
        "damage_scale": 0.75,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.0
      },
      "JAK_Mag_05": {
        "heatimpulse_value": 0.1,
        "firerate_scale": 1.25,
        "damage_scale": 0.6875,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.5,
        "maxloadedammo_value": 8.0
      },
      "DAD_Mag_01": {
        "heatimpulse_value": 0.15,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 8.0
      },
      "DAD_Mag_02": {
        "heatimpulse_value": 0.125,
        "damage_scale": 0.9875,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 10.0
      },
      "DAD_Mag_03": {
        "heatimpulse_value": 0.1,
        "firerate_scale": 0.85,
        "damage_scale": 1.4,
        "reloadtime_value": 2.2,
        "maxloadedammo_value": 6.0
      },
      "DAD_Mag_04": {
        "heatimpulse_value": 0.1,
        "recoil_scale": 1.2,
        "spread_scale": 1.2,
        "damage_scale": 1.0625,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.5
      },
      "DAD_Mag_05": {
        "heatimpulse_value": 0.115,
        "firerate_scale": 1.25,
        "damage_scale": 0.9875,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.1,
        "maxloadedammo_value": 12.0
      },
      "BOR_Mag_01": {
        "heatimpulse_value": 0.1,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 15.0
      },
      "BOR_Mag_02": {
        "heatimpulse_value": 0.05,
        "damage_scale": 0.95,
        "reloadtime_value": 2.6,
        "maxloadedammo_value": 20.0
      },
      "BOR_Mag_03": {
        "heatimpulse_value": 0.1,
        "firerate_scale": 0.875,
        "damage_scale": 1.4375,
        "reloadtime_value": 2.6,
        "maxloadedammo_value": 10.0
      },
      "BOR_Mag_04": {
        "heatimpulse_value": 0.05,
        "recoil_scale": 1.2,
        "spread_scale": 1.2,
        "damage_scale": 0.995,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.2
      },
      "MAL_Mag_01": {
        "heatimpulse_value": 0.25,
        "damage_scale": 1.05,
        "thrownreloadtime_value": 1.65,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 6.0
      },
      "MAL_Mag_02": {
        "heatimpulse_value": 0.2,
        "spread_scale": 1.25,
        "thrownreloadtime_value": 1.65,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 8.0
      },
      "MAL_Mag_03": {
        "heatimpulse_value": 0.35,
        "firerate_scale": 0.825,
        "damage_scale": 1.38,
        "thrownreloadtime_value": 1.65,
        "reloadtime_value": 2.2,
        "maxloadedammo_value": 4.0
      },
      "MAL_Mag_04": {
        "heatimpulse_value": 0.125,
        "recoil_scale": 1.2,
        "spread_scale": 1.2,
        "damage_scale": 1.0625,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.5
      },
      "MAL_Mag_05": {
        "heatimpulse_value": 0.15,
        "firerate_scale": 1.25,
        "damage_scale": 0.9375,
        "thrownreloadtime_value": 2.5,
        "reloadtime_value": 2.75,
        "maxloadedammo_value": 10.0
      },
      "TED_Mag_01": {
        "heatimpulse_value": 0.08,
        "damage_scale": 1.025,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 8.0
      },
      "TED_Mag_02": {
        "heatimpulse_value": 0.05,
        "damage_scale": 0.975,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 10.0
      },
      "TED_Mag_03": {
        "heatimpulse_value": 0.1,
        "firerate_scale": 0.8,
        "damage_scale": 1.3625,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 6.0
      },
      "TED_Mag_04": {
        "heatimpulse_value": 0.125,
        "sway_scale": 1.2,
        "recoil_scale": 1.2,
        "spread_scale": 1.2,
        "damage_scale": 1.0375,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.0
      },
      "TED_Mag_05": {
        "heatimpulse_value": 0.06,
        "firerate_scale": 1.25,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.6,
        "maxloadedammo_value": 12.0
      },
      "TOR_Mag_01": {
        "heatimpulse_value": 0.25,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 8.0
      },
      "TOR_Mag_02": {
        "heatimpulse_value": 0.17,
        "damage_scale": 0.9,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 12.0
      },
      "TOR_Mag_04": {
        "heatimpulse_value": 0.125,
        "sway_scale": 1.2,
        "recoil_scale": 1.2,
        "spread_scale": 1.2,
        "damage_scale": 0.925,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.25
      },
      "TOR_Mag_05": {
        "heatimpulse_value": 0.1,
        "firerate_scale": 1.25,
        "damage_scale": 0.89,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 10.0
      }
    }
  },
  "Weapon_SM_Magazine_Init": {
    "table_name": "Weapon_SM_Magazine_Init",
    "rows": {
      "VLA_Mag_01": {
        "heatimpulse_value": 0.028571,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 30.0
      },
      "VLA_Mag_02": {
        "heatimpulse_value": 0.0225,
        "damage_scale": 1.15,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 3.5,
        "maxloadedammo_value": 35.0
      },
      "VLA_Mag_03": {
        "heatimpulse_value": 0.045,
        "recoil_scale": 1.2,
        "spread_scale": 0.9,
        "firerate_scale": 0.75,
        "damage_scale": 1.3,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 2.2,
        "maxloadedammo_value": 25.0
      },
      "VLA_Mag_04": {
        "heatimpulse_value": 0.025,
        "sway_scale": 1.35,
        "recoil_scale": 1.1,
        "spread_scale": 1.4,
        "damage_scale": 1.09,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 4.35
      },
      "VLA_Mag_05": {
        "heatimpulse_value": 0.038,
        "firerate_scale": 1.15,
        "thrownreloadtime_value": 2.5,
        "reloadtime_value": 2.25,
        "maxloadedammo_value": 40.0
      },
      "DAD_Mag_01": {
        "heatimpulse_value": 0.05,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 2.25,
        "maxloadedammo_value": 22.0
      },
      "DAD_Mag_02": {
        "heatimpulse_value": 0.035,
        "damage_scale": 0.95,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 2.6,
        "maxloadedammo_value": 28.0
      },
      "DAD_Mag_03": {
        "heatimpulse_value": 0.06,
        "recoil_scale": 1.25,
        "spread_scale": 0.9,
        "accuracy_scale": 0.9,
        "firerate_scale": 0.9,
        "damage_scale": 1.34,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 2.8,
        "maxloadedammo_value": 18.0
      },
      "DAD_Mag_04": {
        "heatimpulse_value": 0.03,
        "sway_scale": 1.05,
        "recoil_scale": 1.4,
        "spread_scale": 1.4,
        "accuracy_scale": 1.15,
        "damage_scale": 1.04,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 4.0
      },
      "DAD_Mag_05_B01": {
        "heatimpulse_value": 0.06,
        "firerate_scale": 0.8375,
        "damage_scale": 1.075,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.3,
        "maxloadedammo_value": 32.0
      },
      "DAD_Mag_05_B02": {
        "heatimpulse_value": 0.06,
        "firerate_scale": 0.85,
        "damage_scale": 1.075,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.3,
        "maxloadedammo_value": 32.0
      },
      "BOR_Mag_01": {
        "heatimpulse_value": 0.03,
        "reloadtime_value": 2.1,
        "maxloadedammo_value": 25.0
      },
      "BOR_Mag_02": {
        "heatimpulse_value": 0.03,
        "reloadtime_value": 2.65,
        "maxloadedammo_value": 30.0
      },
      "BOR_Mag_03": {
        "heatimpulse_value": 0.04,
        "firerate_scale": 0.85,
        "damage_scale": 1.2875,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 20.0
      },
      "BOR_Mag_04": {
        "heatimpulse_value": 0.04,
        "recoil_scale": 1.4,
        "spread_scale": 1.4,
        "damage_scale": 1.0625,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.1
      },
      "MAL_Mag_01": {
        "heatimpulse_value": 0.08,
        "reloadtime_value": 2.2,
        "maxloadedammo_value": 28.0
      },
      "MAL_Mag_02": {
        "heatimpulse_value": 0.065,
        "damage_scale": 0.975,
        "reloadtime_value": 2.7,
        "maxloadedammo_value": 36.0
      },
      "MAL_Mag_03": {
        "heatimpulse_value": 0.08,
        "firerate_scale": 0.8,
        "damage_scale": 1.3,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 24.0
      },
      "MAL_Mag_04": {
        "heatimpulse_value": 0.0275,
        "recoil_scale": 1.15,
        "spread_scale": 1.4,
        "damage_scale": 1.025,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.4
      },
      "MAL_Mag_05": {
        "heatimpulse_value": 0.03,
        "recoil_scale": 1.15,
        "spread_scale": 1.25,
        "firerate_scale": 1.2,
        "damage_scale": 0.9125,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.0,
        "maxloadedammo_value": 40.0
      }
    }
  },
  "Weapon_SM_Underbarrel_Init": {
    "table_name": "Weapon_SM_Underbarrel_Init",
    "rows": {
      "DAD_Launcher": {
        "impactforce_value": 30000.0,
        "heatimpulse_value": 0.4,
        "modereturn_scale": 0.8,
        "modeswitch_scale": 1.45,
        "damageradius_value": 300.0,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 14.0,
        "spread_value": 2.0,
        "firerate_value": 2.0,
        "damage_value": 150.0
      },
      "DAD_Shotgun": {
        "impactforce_value": 6000.0,
        "projectilespershot_value": 5.0,
        "heatimpulse_value": 0.1,
        "sway_scale": 1.25,
        "accimpulse_value": 1.75,
        "accuracy_value": 3.0,
        "ammodelay_value": 22.0,
        "ammoregen_value": 8.0,
        "ammo_value": 8.0,
        "spread_value": 10.0,
        "firerate_value": 1.5,
        "damage_value": 12.0
      },
      "DAD_SecondBarrel": {
        "impactforce_value": 12500.0,
        "heatimpulse_value": 0.9,
        "modereturn_scale": 0.9,
        "modeswitch_scale": 0.9,
        "sway_scale": 1.25,
        "recoil_scale": 1.35,
        "accimpulse_value": 0.3,
        "accuracy_value": 1.5,
        "ammodelay_value": 0.5,
        "ammoregen_value": 0.0,
        "ammo_value": 0.0,
        "spread_value": 7.0,
        "firerate_value": 16.0,
        "damage_value": 12.0
      },
      "DAD_Atlas": {
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.1,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "DAD_Atlas_Ball": {
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.1,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "DAD_AmmoSwitcher": {
        "modereturn_scale": 1.1,
        "modeswitch_scale": 1.1
      },
      "DAD_MalElement": {
        "projectilespershot_value": 0.0,
        "modereturn_scale": 0.8,
        "modeswitch_scale": 0.8,
        "sway_scale": 0.0,
        "recoil_scale": 0.0,
        "accregen_value": 0.0,
        "accdelay_value": 0.0,
        "accimpulse_value": 0.0,
        "ammodelay_value": 0.0,
        "ammoregen_value": 0.0,
        "ammo_value": 0.0,
        "damage_value": 0.0
      },
      "VLA_Microrockets": {
        "heatimpulse_value": 0.05,
        "modeswitch_scale": 0.85,
        "sway_scale": 1.25,
        "damageradius_value": 150.0,
        "accdelay_value": 0.75,
        "accimpulse_value": 0.25,
        "accuracy_value": 3.0,
        "ammodelay_value": 24.0,
        "ammoregen_value": 100.0,
        "ammo_value": 20.0,
        "spread_value": 5.0,
        "firerate_value": 5.0,
        "damage_value": 26.0
      },
      "VLA_Taser": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.1,
        "modeswitch_scale": 1.1,
        "damageradius_value": 5.0,
        "accimpulse_value": 1.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 22.0,
        "spread_value": 3.0,
        "firerate_value": 3.0,
        "damage_value": 18.0
      },
      "VLA_Flamethrower": {
        "impactforce_value": 5000.0,
        "heatimpulse_value": 0.02,
        "sway_scale": 1.5,
        "recoil_scale": 0.5,
        "accdelay_value": 1.0,
        "accimpulse_value": 0.05,
        "ammodelay_value": 16.0,
        "ammoregen_value": 8.0,
        "ammo_value": 64.0,
        "spread_value": 4.0,
        "firerate_value": 8.0,
        "damage_value": 5.0
      },
      "VLA_SecondBarrel_Scale": {
        "sway_scale": 1.3,
        "recoil_scale": 0.85,
        "accregen_value": 0.0,
        "accdelay_value": 0.0,
        "accimpulse_value": 0.0,
        "accuracy_value": 1.5,
        "ammodelay_value": 0.0,
        "ammoregen_value": 0.0,
        "ammo_value": 0.0,
        "spread_value": 2.0,
        "firerate_value": 1.75
      },
      "VLA_Atlas": {
        "projectilespershot_value": 5.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 0.9,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "VLA_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 0.9,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "VLA_AmmoSwitcher": {
        "modereturn_scale": 1.8,
        "modeswitch_scale": 1.8
      },
      "VLA_MalElement": {
        "modeswitch_scale": 1.16
      },
      "BOR_ShrapnelCannon": {
        "impactforce_value": 7500.0,
        "projectilespershot_value": 8.0,
        "heatimpulse_value": 0.25,
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2,
        "accimpulse_value": 2.0,
        "accuracy_value": 4.0,
        "ammodelay_value": 15.0,
        "ammo_value": 3.0,
        "spread_value": 8.0,
        "firerate_value": 1.5,
        "damage_value": 30.0
      },
      "BOR_DrunkRocket": {
        "impactforce_value": 30000.0,
        "heatimpulse_value": 0.15,
        "modeswitch_scale": 1.2,
        "damageradius_value": 400.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 24.0,
        "ammoregen_value": 24.0,
        "ammo_value": 12.0,
        "spread_value": 5.0,
        "firerate_value": 4.5,
        "damage_value": 50.0
      },
      "BOR_GasTrap": {
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2,
        "damageradius_value": 400.0,
        "accuracy_value": 6.0,
        "ammodelay_value": 21.0,
        "ammo_value": 3.0,
        "spread_value": 2.0,
        "firerate_value": 1.5,
        "damage_value": 25.0
      },
      "BOR_Atlas": {
        "projectilespershot_value": 5.0,
        "modereturn_scale": 1.3,
        "modeswitch_scale": 1.3,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "BOR_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "modereturn_scale": 1.3,
        "modeswitch_scale": 1.3,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "BOR_AmmoSwitcher": {
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2
      },
      "BOR_MalElement": {
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2
      },
      "MAL_Cutsman": {
        "heatimpulse_value": 0.15,
        "modeswitch_scale": 1.1,
        "damageradius_value": 50.0,
        "accimpulse_value": 0.35,
        "accuracy_value": 2.0,
        "ammodelay_value": 24.0,
        "ammo_value": 4.0,
        "spread_value": 4.0,
        "firerate_value": 2.0,
        "damage_value": 64.0
      },
      "MAL_Overcharge": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.5,
        "modereturn_scale": 0.85,
        "damageradius_value": 1200.0,
        "accuracy_value": 2.25,
        "ammodelay_value": 16.0,
        "spread_value": 3.75,
        "firerate_value": 1.0,
        "damage_value": 115.0
      },
      "MAL_Railgun": {
        "impactforce_value": 30000.0,
        "heatimpulse_value": 0.3,
        "modeswitch_scale": 1.1,
        "damageradius_value": 100.0,
        "accimpulse_value": 0.5,
        "accuracy_value": 4.5,
        "ammoregen_value": 2.0,
        "ammo_value": 2.0,
        "spread_value": 2.5,
        "firerate_value": 1.0,
        "damage_value": 155.0
      },
      "MAL_Atlas": {
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.1,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 4.0
      },
      "MAL_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.1,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 4.0
      },
      "MAL_AmmoSwitcher": {
        "modereturn_scale": 0.9,
        "modeswitch_scale": 0.9
      },
      "MAL_MalElement": {
        "modereturn_scale": 0.8,
        "modeswitch_scale": 0.8
      }
    }
  },
  "Weapon_SR_Barrel_Init": {
    "table_name": "Weapon_SR_Barrel_Init",
    "rows": {
      "JAK_Barrel_01": {
        "part_value": 1.0,
        "sway_scale": 1.25,
        "recoil_scale": 1.15,
        "accdelay_value": 0.85,
        "accimpulse_value": 1.25,
        "accuracy_value": 3.25,
        "spread_value": 1.25,
        "firerate_value": 1.1,
        "damage_scale": 9.7
      },
      "JAK_Barrel_02": {
        "part_value": 2.0,
        "accregen_value": -7.5,
        "accdelay_value": 1.25,
        "accimpulse_value": 1.1,
        "accuracy_value": 4.0,
        "spread_value": 0.95,
        "firerate_value": 0.8,
        "damage_scale": 11.7
      },
      "MAL_Barrel_01": {
        "part_value": 1.0,
        "damageradius_value": 20.0,
        "statusdamage_scale": 1.5,
        "sway_scale": 0.3,
        "accregen_value": -4.0,
        "accdelay_value": 0.8,
        "accimpulse_value": 0.65,
        "accuracy_value": 3.75,
        "spread_value": 1.5,
        "firerate_value": 6.6,
        "damage_scale": 5.3
      },
      "MAL_Barrel_02": {
        "part_value": 2.0,
        "damageradius_value": 40.0,
        "statusdamage_scale": 1.5,
        "sway_scale": 0.9,
        "recoil_scale": 0.6,
        "accdelay_value": 0.6,
        "accimpulse_value": 0.3,
        "accuracy_value": 3.25,
        "spread_value": 1.3,
        "firerate_value": 3.0,
        "damage_scale": 5.9
      },
      "BOR_Barrel_01": {
        "part_value": 1.0,
        "accimpulse_value": 0.6,
        "accuracy_value": 4.0,
        "spread_value": 1.5,
        "firerate_value": 2.25,
        "damage_scale": 4.8
      },
      "BOR_Barrel_02": {
        "part_value": 2.0,
        "sway_scale": 0.9,
        "recoil_scale": 1.1,
        "accregen_value": -7.5,
        "accdelay_value": 0.6,
        "accimpulse_value": 1.1,
        "accuracy_value": 6.0,
        "spread_value": 1.4,
        "firerate_value": 1.5,
        "damage_scale": 5.65
      },
      "VLA_Barrel_01": {
        "part_value": 1.0,
        "accdelay_value": 0.35,
        "accimpulse_value": 1.0,
        "accuracy_value": 5.0,
        "spread_value": 1.75,
        "firerate_value": 4.0,
        "damage_scale": 2.9
      },
      "VLA_Barrel_02": {
        "part_value": 2.0,
        "sway_scale": 0.85,
        "recoil_scale": 1.25,
        "accimpulse_value": 1.3,
        "accuracy_value": 5.5,
        "spread_value": 1.6,
        "firerate_value": 2.5,
        "damage_scale": 3.8
      },
      "ORD_Barrel_01": {
        "part_value": 1.0,
        "accregen_value": -6.0,
        "accdelay_value": 0.75,
        "accimpulse_value": 1.0,
        "accuracy_value": 4.5,
        "spread_value": 1.2,
        "firerate_value": 1.9,
        "damage_scale": 5.4
      },
      "ORD_Barrel_02": {
        "part_value": 2.0,
        "recoil_scale": 1.2,
        "accregen_value": -6.0,
        "accdelay_value": 0.9,
        "accimpulse_value": 0.7,
        "accuracy_value": 5.5,
        "spread_value": 0.95,
        "firerate_value": 1.5,
        "damage_scale": 6.5
      }
    }
  },
  "Weapon_SR_Magazine_Init": {
    "table_name": "Weapon_SR_Magazine_Init",
    "rows": {
      "JAK_Mag_01": {
        "heatimpulse_value": 0.18,
        "sway_scale": 1.2,
        "damage_scale": 0.95,
        "reloadtime_value": 3.5,
        "maxloadedammo_value": 6.0
      },
      "JAK_Mag_02": {
        "heatimpulse_value": 0.15,
        "reloadtime_value": 2.8,
        "maxloadedammo_value": 4.0
      },
      "JAK_Mag_03": {
        "heatimpulse_value": 0.1,
        "recoil_scale": 1.3,
        "spread_scale": 0.9,
        "firerate_scale": 0.85,
        "damage_scale": 0.9875,
        "reloadtime_value": 3.0,
        "maxloadedammo_value": 10.0
      },
      "JAK_Mag_04": {
        "heatimpulse_value": 0.1111,
        "sway_scale": 1.25,
        "spread_scale": 1.3,
        "accuracy_scale": 1.3,
        "damage_scale": 0.8625,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 4.0
      },
      "JAK_Mag_05": {
        "heatimpulse_value": 0.15,
        "firerate_scale": 1.3,
        "damage_scale": 0.825,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.1,
        "maxloadedammo_value": 8.0
      },
      "MAL_Mag_01": {
        "heatimpulse_value": 0.2,
        "reloadtime_value": 2.65,
        "maxloadedammo_value": 8.0
      },
      "MAL_Mag_02": {
        "heatimpulse_value": 0.166,
        "reloadtime_value": 3.15,
        "maxloadedammo_value": 10.0
      },
      "MAL_Mag_03": {
        "heatimpulse_value": 0.2,
        "firerate_scale": 0.8,
        "damage_scale": 1.2625,
        "reloadtime_value": 2.2,
        "maxloadedammo_value": 6.0
      },
      "MAL_Mag_04": {
        "heatimpulse_value": 0.1,
        "sway_scale": 0.95,
        "recoil_scale": 0.95,
        "spread_scale": 1.4,
        "accuracy_scale": 1.4,
        "damage_scale": 0.9825,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.75
      },
      "MAL_Mag_05_B01": {
        "heatimpulse_value": 0.2,
        "spread_scale": 1.15,
        "accuracy_scale": 1.15,
        "firerate_scale": 0.35,
        "damage_scale": 0.9,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 12.0
      },
      "MAL_Mag_05_B02": {
        "heatimpulse_value": 0.2,
        "spread_scale": 1.15,
        "accuracy_scale": 1.15,
        "firerate_scale": 1.2,
        "damage_scale": 0.9,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.4,
        "maxloadedammo_value": 12.0
      },
      "BOR_Mag_01": {
        "heatimpulse_value": 0.125,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 2.87,
        "maxloadedammo_value": 10.0
      },
      "BOR_Mag_02": {
        "heatimpulse_value": 0.1,
        "damage_scale": 0.9,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 3.1,
        "maxloadedammo_value": 15.0
      },
      "BOR_Mag_03": {
        "heatimpulse_value": 0.2,
        "firerate_scale": 0.8,
        "damage_scale": 1.25,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 2.3,
        "maxloadedammo_value": 8.0
      },
      "BOR_Mag_04": {
        "heatimpulse_value": 0.0675,
        "damage_scale": 0.925,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 4.0
      },
      "VLA_Mag_01": {
        "heatimpulse_value": 0.08,
        "reloadtime_value": 3.0,
        "maxloadedammo_value": 12.0
      },
      "VLA_Mag_02": {
        "heatimpulse_value": 0.067,
        "reloadtime_value": 3.6,
        "maxloadedammo_value": 15.0
      },
      "VLA_Mag_03": {
        "heatimpulse_value": 0.1,
        "firerate_scale": 0.825,
        "damage_scale": 1.2875,
        "reloadtime_value": 2.85,
        "maxloadedammo_value": 9.0
      },
      "VLA_Mag_04": {
        "heatimpulse_value": 0.0725,
        "recoil_scale": 1.4,
        "spread_scale": 1.3,
        "accuracy_scale": 1.3,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 4.25
      },
      "VLA_Mag_05": {
        "heatimpulse_value": 0.067,
        "firerate_scale": 1.25,
        "damage_scale": 0.9875,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.6,
        "maxloadedammo_value": 18.0
      },
      "ORD_Mag_01": {
        "heatimpulse_value": 0.2,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 2.3,
        "maxloadedammo_value": 12.0
      },
      "ORD_Mag_02": {
        "heatimpulse_value": 0.15,
        "damage_scale": 0.975,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 2.7,
        "maxloadedammo_value": 15.0
      },
      "ORD_Mag_03": {
        "heatimpulse_value": 0.2,
        "firerate_scale": 0.8,
        "damage_scale": 1.275,
        "thrownreloadtime_value": 1.6,
        "reloadtime_value": 2.1,
        "maxloadedammo_value": 9.0
      },
      "ORD_Mag_04": {
        "heatimpulse_value": 0.05,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 3.7
      },
      "ORD_Mag_05": {
        "heatimpulse_value": 0.1,
        "firerate_scale": 1.2,
        "damage_scale": 0.9,
        "thrownreloadtime_value": 3.0,
        "reloadtime_value": 2.1,
        "maxloadedammo_value": 18.0
      }
    }
  },
  "Weapon_SR_Underbarrel_Init": {
    "table_name": "Weapon_SR_Underbarrel_Init",
    "rows": {
      "JAK_Shotgun": {
        "impactforce_value": 3750.0,
        "projectilespershot_value": 8.0,
        "heatimpulse_value": 0.25,
        "accimpulse_value": 1.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 16.0,
        "ammoregen_value": 3.0,
        "ammo_value": 3.0,
        "spread_value": 8.0,
        "firerate_value": 1.25,
        "damage_value": 15.0
      },
      "JAK_Rocket": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.5,
        "modeswitch_scale": 1.1,
        "damageradius_value": 400.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 30.0,
        "spread_value": 2.0,
        "firerate_value": 2.0,
        "damage_value": 165.0
      },
      "JAK_Crank": {
        "heatimpulse_value": 0.04,
        "modereturn_scale": 0.96,
        "modeswitch_scale": 0.9,
        "accuracy_value": 3.0,
        "ammodelay_value": 24.0,
        "ammoregen_value": 24.0,
        "ammo_value": 24.0,
        "spread_value": 5.0,
        "firerate_value": 6.0,
        "damage_value": 24.0
      },
      "JAK_Atlas": {
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.2,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 8.0,
        "spread_value": 4.0,
        "firerate_value": 2.0
      },
      "JAK_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.5,
        "accuracy_value": 2.0,
        "ammodelay_value": 10.0,
        "spread_value": 2.0,
        "firerate_value": 2.0
      },
      "JAK_AmmoSwitcher": {
        "modereturn_scale": 1.167,
        "modeswitch_scale": 1.35
      },
      "MAL_Singularity": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.3,
        "damageradius_value": 350.0,
        "accimpulse_value": 1.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 40.0,
        "spread_value": 5.0,
        "firerate_value": 2.0,
        "damage_value": 10.0
      },
      "MAL_Multitaser": {
        "heatimpulse_value": 0.35,
        "damageradius_value": 350.0,
        "accuracy_value": 3.0,
        "ammo_value": 2.0,
        "spread_value": 2.5,
        "firerate_value": 2.0,
        "damage_value": 20.0
      },
      "MAL_RocketPod": {
        "impactforce_value": 30000.0,
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.1,
        "modeswitch_scale": 1.1,
        "damageradius_value": 100.0,
        "accimpulse_value": 0.3,
        "accuracy_value": 3.0,
        "ammodelay_value": 16.0,
        "ammoregen_value": 4.0,
        "ammo_value": 16.0,
        "spread_value": 5.0,
        "firerate_value": 1.5,
        "damage_value": 26.0
      },
      "MAL_Atlas": {
        "projectilespershot_value": 7.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.25,
        "modeswitch_scale": 1.25,
        "spread_value": 4.0,
        "firerate_value": 1.0
      },
      "MAL_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.25,
        "modeswitch_scale": 1.25,
        "damageradius_value": 350.0,
        "spread_value": 4.0,
        "firerate_value": 1.0
      },
      "MAL_AmmoSwitcher": {
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125
      },
      "BOR_GravTrap": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.4,
        "modereturn_scale": 1.1,
        "modeswitch_scale": 1.2,
        "damageradius_value": 600.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 36.0,
        "spread_value": 3.0,
        "firerate_value": 2.0,
        "damage_value": 60.0
      },
      "BOR_Seeker": {
        "impactforce_value": 30000.0,
        "projectilespershot_value": 4.0,
        "heatimpulse_value": 0.1,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "damageradius_value": 100.0,
        "accimpulse_value": 0.6,
        "accuracy_value": 5.0,
        "ammodelay_value": 15.0,
        "ammoregen_value": 4.0,
        "ammo_value": 12.0,
        "spread_value": 8.0,
        "firerate_value": 2.0,
        "damage_value": 12.0
      },
      "BOR_Marked": {
        "impactforce_value": 5000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "damageradius_value": 200.0,
        "accuracy_value": 5.0,
        "spread_value": 2.0,
        "firerate_value": 2.0,
        "damage_value": 50.0
      },
      "BOR_Atlas": {
        "projectilespershot_value": 3.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "accuracy_value": 3.0,
        "spread_value": 4.0,
        "firerate_value": 1.0
      },
      "BOR_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.5,
        "modeswitch_scale": 1.5,
        "damageradius_value": 350.0,
        "accuracy_value": 3.0,
        "spread_value": 2.0,
        "firerate_value": 1.0
      },
      "BOR_AmmoSwitcher": {
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125
      },
      "BOR_MalElement": {
        "modereturn_scale": 1.3,
        "modeswitch_scale": 1.3
      },
      "VLA_Shotgun": {
        "impactforce_value": 5000.0,
        "projectilespershot_value": 6.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.05,
        "modeswitch_scale": 1.05,
        "accuracy_value": 3.0,
        "ammodelay_value": 12.0,
        "ammo_value": 6.0,
        "spread_value": 5.0,
        "firerate_value": 3.0,
        "damage_value": 10.0
      },
      "VLA_Rocket": {
        "impactforce_value": 100000.0,
        "heatimpulse_value": 0.4,
        "modeswitch_scale": 1.2,
        "damageradius_value": 600.0,
        "accimpulse_value": 0.35,
        "accuracy_value": 4.0,
        "ammodelay_value": 30.0,
        "spread_value": 4.5,
        "firerate_value": 2.0,
        "damage_value": 165.0
      },
      "VLA_Bipod": {
        "modereturn_scale": 0.9,
        "sway_scale": 0.25,
        "recoil_scale": 0.25,
        "accimpulse_value": 0.25,
        "accuracy_value": 0.75,
        "spread_value": 0.75,
        "firerate_value": 2.0
      },
      "VLA_ExtraBarrel": {
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2,
        "accuracy_value": 0.5,
        "spread_value": 0.25,
        "firerate_value": 0.667
      },
      "VLA_Atlas": {
        "projectilespershot_value": 5.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.125,
        "accuracy_value": 2.0,
        "spread_value": 4.0,
        "firerate_value": 1.0
      },
      "VLA_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.125,
        "damageradius_value": 350.0,
        "accuracy_value": 2.5,
        "spread_value": 2.0,
        "firerate_value": 1.0
      },
      "VLA_AmmoSwitcher": {
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125
      },
      "ORD_Spear": {
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125,
        "damageradius_value": 350.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 36.0,
        "ammoregen_value": 2.0,
        "ammo_value": 2.0,
        "spread_value": 3.0,
        "firerate_value": 2.0,
        "damage_value": 120.0
      },
      "ORD_Tether_Snare": {
        "impactforce_value": 30000.0,
        "heatimpulse_value": 0.3,
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125,
        "damageradius_value": 50.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 24.0,
        "ammoregen_value": 3.0,
        "ammo_value": 3.0,
        "spread_value": 3.0,
        "firerate_value": 2.0,
        "damage_value": 12.0
      },
      "ORD_Railgun": {
        "impactforce_value": 30000.0,
        "projectilespershot_value": 2.0,
        "heatimpulse_value": 0.2,
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125,
        "damageradius_value": 150.0,
        "accuracy_value": 2.0,
        "ammodelay_value": 24.0,
        "ammoregen_value": 3.0,
        "ammo_value": 3.0,
        "spread_value": 3.0,
        "firerate_value": 1.0,
        "damage_value": 70.0
      },
      "ORD_Atlas": {
        "projectilespershot_value": 6.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.2,
        "recoil_scale": 0.1,
        "accuracy_value": 3.0,
        "ammoregen_value": 6.0,
        "spread_value": 3.0,
        "firerate_value": 2.0
      },
      "ORD_Atlas_Ball": {
        "impactforce_value": 10000.0,
        "heatimpulse_value": 0.2,
        "modeswitch_scale": 1.2,
        "damageradius_value": 350.0,
        "accuracy_value": 2.5,
        "spread_value": 3.5,
        "firerate_value": 2.0
      },
      "ORD_AmmoSwitcher": {
        "modereturn_scale": 1.125,
        "modeswitch_scale": 1.125
      }
    }
  },
  "Weapon_Unique_AR_Init": {
    "table_name": "Weapon_Unique_AR_Init",
    "rows": {
      "TOR_Bugbear": {
        "value_4": 6.0,
        "custom_4_desc": "Finale Damage Radius Scale",
        "value_3": 3.0,
        "custom_3_desc": "Finale Damage Scale",
        "value_2": 2.0,
        "custom_2_desc": "Max Damage Radius Scale",
        "value_1": 1.0,
        "custom_1_desc": "Max Damage Scale"
      },
      "ORD_Goalkeeper": {
        "value_5": 15.0,
        "custom_5_desc": "Amp Duration",
        "value_4": 0.5,
        "custom_4_desc": "Amp Damage Scale",
        "value_3": -2.0,
        "custom_3_desc": "Weapon Charge Scale",
        "value_2": 0.9,
        "custom_2_desc": "Weapon Shield Delay Scale",
        "value_1": 1.0,
        "custom_1_desc": "Weapon Shield Capacity Scale"
      },
      "ORD_Goalkeeper_2": {
        "value_1": 0.5,
        "custom_1_desc": "AmmoScaleAdd"
      },
      "VLA_WomboCombo": {
        "value_1": 8.0,
        "custom_1_desc": "rocket dmg scalar"
      },
      "JAK_BonnieClyde": {
        "value_1": 1.0,
        "custom_1_desc": "Damage buff"
      },
      "TED_Chuck": {
        "value_4": 2.0,
        "custom_4_desc": "firerate scale",
        "value_3": 10.0,
        "custom_3_desc": "ammo override",
        "value_2": -2.0,
        "custom_2_desc": "Reload time scale",
        "value_1": 4.0,
        "custom_1_desc": "TED throw dmg scale"
      },
      "VLA_Lucian": {
        "value_3": 10.0,
        "custom_3_desc": "Post Added Mag Size",
        "value_2": 2.0,
        "custom_2_desc": "Ammo Regen on Crit",
        "value_1": 1.0,
        "custom_1_desc": "Extra Ricochets"
      },
      "JAK_Rowan": {
        "value_3": 2.5,
        "custom_3_desc": "MagSzieScale",
        "value_2": 2.0,
        "custom_2_desc": "AmmoRegenOnCrit",
        "value_1": 0.2,
        "custom_1_desc": "CritChance"
      },
      "ORD_GMR": {
        "value_4": 3.0,
        "custom_4_desc": "MagSizePostAdd",
        "value_3": -1.0,
        "custom_3_desc": "ZoomFireRateScaleAdd",
        "value_2": 1.0,
        "custom_2_desc": "ZoomShotCostScaleAdd",
        "value_1": 1.0,
        "custom_1_desc": "ZoomDamageScaleAdd"
      },
      "DAD_FirstImpression": {
        "value_1": 0.5,
        "custom_1_desc": "Chance to Crit over 50% health"
      }
    }
  },
  "Weapon_Unique_Magazine_Init": {
    "table_name": "Weapon_Unique_Magazine_Init",
    "rows": {
      "JAK_Mag_01": {
        "heatimpulse_value": 0.165,
        "reloadtime_value": 2.35,
        "maxloadedammo_value": 4.0
      },
      "JAK_Mag_02": {
        "heatimpulse_value": 0.12,
        "reloadtime_value": 2.25,
        "maxloadedammo_value": 6.0
      },
      "ORD_PS_NoisyCricket": {
        "reloadtime_value": 1.5,
        "maxloadedammo_value": 2.0
      },
      "JAK_SG_RainbowVomit": {
        "heatimpulse_value": 0.16,
        "reloadtime_value": 2.15,
        "maxloadedammo_value": 6.0
      },
      "ORD_PS_Rocket": {
        "heatimpulse_value": 0.2,
        "reloadtime_value": 1.9,
        "maxloadedammo_value": 6.0
      },
      "PRD_SR_Fisheye": {
        "maxloadedammo_value": 3.0
      }
    }
  },
  "Weapon_Unique_PS_Init": {
    "table_name": "Weapon_Unique_PS_Init",
    "rows": {
      "ORD_Bully": {
        "value_3": 1.2,
        "custom_3_desc": "drone dmg scalar",
        "value_2": 14.0,
        "custom_2_desc": "drone cooldown",
        "value_1": 0.3,
        "custom_1_desc": "mag size"
      },
      "TOR_Roach": {
        "value_1": 0.6,
        "custom_1_desc": "child proj damage"
      },
      "DAD_Zipgun": {
        "value_2": 0.75,
        "custom_2_desc": "back damage mod",
        "value_1": 0.75,
        "custom_1_desc": "crit damage mod"
      },
      "JAK_KingsGambit": {
        "value_2": 1.0,
        "custom_2_desc": "Ricochet Dmg Scale",
        "value_1": 4.0,
        "custom_1_desc": "Ricochet Count"
      },
      "JAK_SeventhSense": {
        "value_1": 0.5,
        "custom_1_desc": "ChildDmgScale"
      },
      "ORD_Disorder": {
        "value_1": 2.0,
        "custom_1_desc": "ReloadDmgScale"
      },
      "TOR_QueensRest": {
        "value_2": 1.0,
        "custom_2_desc": "ProcDmgScale",
        "value_1": 0.3,
        "custom_1_desc": "Chance"
      },
      "DAD_Rangefinder": {
        "value_4": 2.0,
        "custom_4_desc": "StatusChanceAddPerStack",
        "value_3": 2.0,
        "custom_3_desc": "DmgRadiusAddPerStack",
        "value_2": 2.0,
        "custom_2_desc": "DmgAddPerStack",
        "value_1": -1.0,
        "custom_1_desc": "BurstAddPerStack"
      },
      "TED_Sideshow": {
        "value_2": 5.0,
        "custom_2_desc": "Max stacks",
        "value_1": 0.07,
        "custom_1_desc": "Damage Scalar"
      },
      "JAK_Quickdraw": {
        "value_2": 1.0,
        "custom_2_desc": "DamageScale",
        "value_1": 5.0,
        "custom_1_desc": "Duration"
      },
      "JAK_PhantomFlame": {
        "value_1": 0.5,
        "custom_1_desc": "ReloadTimeScaleA"
      }
    }
  },
  "Weapon_Unique_SG_Init": {
    "table_name": "Weapon_Unique_SG_Init",
    "rows": {
      "JAK_Slugger": {
        "value_5": 10.0,
        "custom_5_desc": "kill stack duration",
        "custom_4_desc": "kill stack reload speed",
        "value_3": 0.3,
        "custom_3_desc": "kill stack damage",
        "value_2": -1.0,
        "custom_2_desc": "reload speed",
        "value_1": 1.0,
        "custom_1_desc": "mag size"
      },
      "TOR_Linebacker": {
        "value_2": 0.35,
        "custom_2_desc": "dmg radius bounce scale",
        "value_1": 0.25,
        "custom_1_desc": "dmg bounce scale"
      },
      "TED_Anarchy": {
        "value_3": 0.15,
        "custom_3_desc": "Accuracy Scale per stack",
        "value_2": 0.15,
        "custom_2_desc": "Dmg Scale per stack",
        "value_1": 20.0,
        "custom_1_desc": "Max Stacks"
      },
      "JAK_Hellwalker": {
        "value_1": 0.6,
        "custom_1_desc": "ReloadTimeScale"
      },
      "BOR_GoreMaster": {
        "value_2": 0.3,
        "custom_2_desc": "Dmg Scalar",
        "value_1": 0.3,
        "custom_1_desc": "LowHP Threshold"
      }
    }
  },
  "Weapon_Unique_SMG_Init": {
    "table_name": "Weapon_Unique_SMG_Init",
    "rows": {
      "DAD_Conglomerate": {
        "value_1": 3.0,
        "custom_1_desc": "TED throw damage scale"
      },
      "MAL_OhmIGot": {
        "value_1": 1.5,
        "custom_1_desc": "damage scale"
      },
      "VLA_Onslaught": {
        "value_3": 0.3,
        "custom_3_desc": "amp dmg mod",
        "value_2": 1.0,
        "custom_2_desc": "mag size",
        "value_1": 0.3,
        "custom_1_desc": "amp shot chance"
      },
      "DAD_Bloodstarved": {
        "value_3": 0.05,
        "custom_3_desc": "ExplosionChance",
        "value_2": 4.0,
        "custom_2_desc": "ExplosinonDmgScale",
        "value_1": 1.5,
        "custom_1_desc": "MagSizeScale"
      },
      "BOR_Prince": {
        "value_3": 0.5,
        "custom_3_desc": "OvershieldScale",
        "value_2": 30.0,
        "custom_2_desc": "Max Stacks",
        "value_1": 0.05,
        "custom_1_desc": "SelfDmgShieldScale"
      },
      "MAL_PlasmaCoil": {
        "value_1": 0.65,
        "custom_1_desc": "ReloadTimeScale"
      }
    }
  },
  "Weapon_Unique_SR_Init": {
    "table_name": "Weapon_Unique_SR_Init",
    "rows": {
      "JAK_Boomslang": {
        "value_1": 3.0,
        "custom_1_desc": "max ricochets"
      },
      "MAL_Katagawa": {
        "value_3": 0.13,
        "custom_3_desc": "Shock beam Damage scale",
        "value_2": 0.5,
        "custom_2_desc": "Fire damage scale",
        "value_1": 300.0,
        "custom_1_desc": "Fire radius"
      },
      "JAK_Ballista": {
        "value_2": 0.35,
        "custom_2_desc": "Child dmg scale",
        "value_1": 2.0,
        "custom_1_desc": "heat impusle scale"
      },
      "VLA_CrowdSourced": {
        "value_3": 5000.0,
        "custom_3_desc": "Query Max Distance",
        "value_2": 10.0,
        "custom_2_desc": "Query Max Actors",
        "value_1": 0.5,
        "custom_1_desc": "Add'l Dmg Scalar"
      }
    }
  },
  "Weapon_Unique_Underbarrel_Init": {
    "table_name": "Weapon_Unique_Underbarrel_Init",
    "rows": {
      "DAD_AR_OM_Grenade": {
        "impactforce_value": 60000.0,
        "heatimpulse_value": 0.25,
        "modereturn_scale": 1.2,
        "modeswitch_scale": 1.2,
        "damageradius_value": 400.0,
        "accdelay_value": 1.0,
        "accimpulse_value": 1.0,
        "accuracy_value": 3.0,
        "ammoregen_value": 3.0,
        "ammo_value": 3.0,
        "spread_value": 1.0,
        "firerate_value": 1.5,
        "damage_value": 120.0
      },
      "DAD_AR_OM_SpaceLaser": {
        "heatimpulse_value": 0.2,
        "damageradius_value": 300.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 60.0,
        "firerate_value": 1.0,
        "damage_value": 200.0
      },
      "VLA_AR_WF_ScrapCannon": {
        "impactforce_value": 10000.0,
        "projectilespershot_value": 6.0,
        "heatimpulse_value": 0.1,
        "modereturn_scale": 0.75,
        "recoil_scale": 1.25,
        "accimpulse_value": 0.35,
        "accuracy_value": 4.0,
        "ammodelay_value": 15.0,
        "ammoregen_value": 4.0,
        "ammo_value": 3.0,
        "spread_value": 5.0,
        "firerate_value": 4.5,
        "damage_value": 8.0
      },
      "VLA_AR_WF_Overdrive": {
        "heatimpulse_value": 0.02,
        "recoil_scale": 0.85,
        "ammodelay_value": 60.0,
        "ammoregen_value": 150.0,
        "ammo_value": 75.0,
        "firerate_value": 10.4
      },
      "TED_SG_HeavyTurret": {
        "heatimpulse_value": 0.2,
        "damageradius_value": 100.0,
        "accuracy_value": 3.0,
        "ammodelay_value": 24.0,
        "spread_value": 4.0,
        "firerate_value": 2.0,
        "damage_value": 4.0
      }
    }
  },
  "WeaponManufacturer_Init": {
    "table_name": "WeaponManufacturer_Init",
    "rows": {
      "Jakobs": {
        "critdamage_add": 0.2,
        "equiptime_scale": 1.0,
        "putdowntime_scale": 1.0,
        "weaponhitforce_scale": 1.25,
        "elementalchance_scale": 1.0,
        "elementaldamage_scale": 1.0,
        "zoomtime_scale": 1.0
      },
      "Daedalus": {
        "critdamage_add": 0.0,
        "equiptime_scale": 0.75,
        "putdowntime_scale": 0.75,
        "weaponhitforce_scale": 1.0,
        "elementalchance_scale": 1.0,
        "elementaldamage_scale": 1.0,
        "zoomtime_scale": 0.85
      },
      "Vladof": {
        "critdamage_add": 0.0,
        "equiptime_scale": 1.0,
        "putdowntime_scale": 1.0,
        "weaponhitforce_scale": 1.0,
        "elementalchance_scale": 1.0,
        "elementaldamage_scale": 1.0,
        "zoomtime_scale": 1.0
      },
      "Maliwan": {
        "critdamage_add": 0.0,
        "equiptime_scale": 1.0,
        "putdowntime_scale": 1.0,
        "weaponhitforce_scale": 1.0,
        "elementalchance_scale": 1.0,
        "elementaldamage_scale": 1.0,
        "zoomtime_scale": 1.0
      },
      "Torgue": {
        "critdamage_add": 0.0,
        "equiptime_scale": 1.0,
        "putdowntime_scale": 1.0,
        "weaponhitforce_scale": 1.0,
        "elementalchance_scale": 1.0,
        "elementaldamage_scale": 1.0,
        "zoomtime_scale": 1.0
      },
      "Tediore": {
        "critdamage_add": 0.0,
        "equiptime_scale": 0.6,
        "putdowntime_scale": 0.6,
        "weaponhitforce_scale": 1.0,
        "elementalchance_scale": 1.0,
        "elementaldamage_scale": 1.0,
        "zoomtime_scale": 0.75
      },
      "Borg": {
        "critdamage_add": 0.0,
        "equiptime_scale": 1.15,
        "putdowntime_scale": 1.15,
        "weaponhitforce_scale": 1.0,
        "elementalchance_scale": 1.0,
        "elementaldamage_scale": 1.0,
        "zoomtime_scale": 1.0
      },
      "Order": {
        "critdamage_add": 0.05,
        "equiptime_scale": 1.0,
        "putdowntime_scale": 1.0,
        "weaponhitforce_scale": 1.0,
        "elementalchance_scale": 1.0,
        "elementaldamage_scale": 1.0,
        "zoomtime_scale": 1.0
      }
    }
  },
  "WeaponType_DamageScale": {
    "table_name": "WeaponType_DamageScale",
    "rows": {
      "Pistol": {
        "daedalus": 1.0,
        "jakobs": 1.0,
        "vladof": 1.0,
        "tediore": 1.0,
        "torgue": 1.0,
        "maliwan": 1.0,
        "borg": 1.0,
        "order": 1.0
      },
      "SMG": {
        "daedalus": 1.0,
        "jakobs": 1.0,
        "vladof": 1.0,
        "tediore": 1.0,
        "torgue": 1.0,
        "maliwan": 1.0,
        "borg": 1.0,
        "order": 1.0
      },
      "Shotgun": {
        "daedalus": 1.0,
        "jakobs": 1.0,
        "vladof": 1.0,
        "tediore": 1.0,
        "torgue": 1.0,
        "maliwan": 1.0,
        "borg": 1.0,
        "order": 1.0
      },
      "AssaultRifle": {
        "daedalus": 1.0,
        "jakobs": 1.0,
        "vladof": 1.0,
        "tediore": 1.0,
        "torgue": 1.0,
        "maliwan": 1.0,
        "borg": 1.0,
        "order": 1.0
      },
      "SniperRifle": {
        "daedalus": 1.0,
        "jakobs": 1.0,
        "vladof": 1.0,
        "tediore": 1.0,
        "torgue": 1.0,
        "maliwan": 1.0,
        "borg": 1.0,
        "order": 1.0
      }
    }
  }
};

if (typeof module !== 'undefined') module.exports = WEAPON_STATS_DATA;
