/**
 * Legacy Class Mod name parts (Name+Skin) for the Guided Class Mod Builder.
 * Merges into __LEGACY_CLASSMOD_PARTS_BY_KEY (safe if skills_full already seeded the object).
 * Format: [id, name, kind] where kind is "Name+Skin" (normal) or "Name+Skin+Leg Effect" (legendary).
 */
(function () {
  'use strict';
  var root = window.__LEGACY_CLASSMOD_PARTS_BY_KEY = window.__LEGACY_CLASSMOD_PARTS_BY_KEY || {};
  var extras = {
    vex: [
      [1, "Transistor", "Name+Skin"], [2, "Firedancer", "Name+Skin"], [3, "Naturalist", "Name+Skin"],
      [4, "Weaver", "Name+Skin"], [5, "Radiance", "Name+Skin"], [6, "Ritualist", "Name+Skin"],
      [7, "Alchemist", "Name+Skin"], [8, "Commander", "Name+Skin"], [9, "Hunter", "Name+Skin"],
      [10, "Technomancer", "Name+Skin+Leg Effect"], [11, "Avatar", "Name+Skin+Leg Effect"],
      [12, "Undead Eye", "Name+Skin+Leg Effect"], [13, "Kindread Spirits", "Name+Skin+Leg Effect"],
      [14, "Illusionist", "Name+Skin+Leg Effect"], [15, "Teen Witch", "Name+Skin+Leg Effect"],
      [538, "Configuration", "Name+Skin+Leg Effect"], [544, "Grim Sister", "Name+Skin+Leg Effect"],
      [546, "Living Weapon", "Name+Skin+Leg Effect"]
    ],
    amon: [
      [1, "Brawler", "Name+Skin"], [2, "Grenadier", "Name+Skin"], [3, "Icebringer", "Name+Skin"],
      [4, "Torchbearer", "Name+Skin"], [5, "Stormcaller", "Name+Skin"], [6, "Soldier", "Name+Skin"],
      [7, "Commando", "Name+Skin"], [8, "Cyborg", "Name+Skin"], [9, "Outlaw", "Name+Skin"],
      [10, "Furnace", "Name+Skin+Leg Effect"], [11, "Elementalist", "Name+Skin+Leg Effect"],
      [12, "Blacksmith", "Name+Skin+Leg Effect"], [13, "Shatterwight", "Name+Skin+Leg Effect"],
      [14, "Viking", "Name+Skin+Leg Effect"], [15, "Forge Master", "Name+Skin+Leg Effect"],
      [538, "Tempest", "Name+Skin+Leg Effect"], [544, "Artificer", "Name+Skin+Leg Effect"],
      [546, "Damned", "Name+Skin+Leg Effect"]
    ],
    rafa: [
      [1, "Genio", "Name+Skin"], [2, "Soldado", "Name+Skin"], [3, "Demolitionist", "Name+Skin"],
      [4, "Tecnico", "Name+Skin"], [5, "Mercenario", "Name+Skin"], [6, "Gearhead", "Name+Skin"],
      [7, "Trooper", "Name+Skin"], [8, "Tanker", "Name+Skin"], [9, "Practitioner", "Name+Skin"],
      [10, "Dancer", "Name+Skin+Leg Effect"], [11, "Filantropo", "Name+Skin+Leg Effect"],
      [12, "Instigator", "Name+Skin+Leg Effect"], [13, "Buster", "Name+Skin+Leg Effect"],
      [14, "Esgrimidor", "Name+Skin+Leg Effect"], [15, "Grenazerker", "Name+Skin+Leg Effect"],
      [540, "Trooper", "Name+Skin+Leg Effect"], [542, "Reaparición", "Name+Skin+Leg Effect"],
      [546, "Bombastic", "Name+Skin+Leg Effect"], [548, "Power-Puncher", "Name+Skin+Leg Effect"]
    ],
    harlowe: [
      [1, "Chemist", "Name+Skin"], [2, "Assistant", "Name+Skin"], [3, "Physicist", "Name+Skin"],
      [4, "Controller", "Name+Skin"], [5, "Compiler", "Name+Skin"], [6, "Specialist", "Name+Skin"],
      [7, "Bookworm", "Name+Skin"], [8, "Radiologist", "Name+Skin"], [9, "Savant", "Name+Skin"],
      [10, "Bio Robot", "Name+Skin+Leg Effect"], [11, "Reactor", "Name+Skin+Leg Effect"],
      [12, "Generator", "Name+Skin+Leg Effect"], [13, "Driver", "Name+Skin+Leg Effect"],
      [14, "Skeptic", "Name+Skin+Leg Effect"], [15, "Scientist", "Name+Skin+Leg Effect"],
      [540, "Trooper", "Name+Skin+Leg Effect"], [542, "Phlebotomist", "Name+Skin+Leg Effect"],
      [546, "Plasmaphile", "Name+Skin+Leg Effect"], [548, "Chirurgeon", "Name+Skin+Leg Effect"]
    ],
    /* C4sh (Robodealer): C4sh class mod names + legendary bodies + skill perks */
    c4sh: [
      [1, "Pistoleer", "Name+Skin"], [2, "Bane", "Name+Skin"], [3, "Gambler", "Name+Skin"], [4, "Puppeteer", "Name+Skin"],
      [5, "Swindler", "Name+Skin"], [6, "Antagonist", "Name+Skin"], [7, "Powderbot", "Name+Skin"], [8, "Triggerbot", "Name+Skin"],
      [9, "CrackShot", "Name+Skin"], [10, "Pack Leader", "Name+Skin"], [11, "Rounder", "Name+Skin+Leg Effect"], [12, "Ludopath", "Name+Skin+Leg Effect"],
      [13, "Hotshot", "Name+Skin+Leg Effect"], [14, "Cooler", "Name+Skin+Leg Effect"], [15, "Whale", "Name+Skin+Leg Effect"], [16, "Trick Shot", "Skill"],
      [17, "Trick Shot", "Skill"], [18, "Trick Shot", "Skill"], [19, "Trick Shot", "Skill"], [20, "Trick Shot", "Skill"],
      [21, "The Determinator", "Skill"], [22, "The Determinator", "Skill"], [23, "The Determinator", "Skill"], [24, "The Determinator", "Skill"],
      [25, "The Determinator", "Skill"], [26, "Double-Down", "Skill"], [27, "Double-Down", "Skill"], [28, "Double-Down", "Skill"],
      [29, "Double-Down", "Skill"], [30, "Double-Down", "Skill"], [46, "Devil's Tine Green", "Skill"], [47, "Devil's Tine Green", "Skill"],
      [48, "Devil's Tine Green", "Skill"], [49, "Devil's Tine Green", "Skill"], [50, "Devil's Tine Green", "Skill"], [51, "Windrider", "Name+Skin+Leg Effect"],
      [57, "Wretched Shadows", "Skill"], [58, "Devil's Tine Blue", "Skill"], [59, "Late Scratch", "Skill"], [60, "Trick-Taker", "Skill"],
      [61, "Sounds of Rain", "Skill"], [62, "Go for Broke", "Skill"], [63, "Alchemy", "Skill"], [64, "Splash the pot", "Skill"],
      [65, "Insurance", "Skill"], [66, "Fast Hands", "Skill"], [67, "Riding High", "Skill"], [68, "Bonemeal Ticket", "Skill"],
      [69, "Before She Knows You're Dead", "Skill"], [70, "Luckless", "Skill"], [71, "Ready to Roll", "Skill"], [72, "Red Moon Rising", "Skill"],
      [73, "O Fortuna", "Skill"], [74, "Charm Bracelet", "Skill"], [76, "Sweet Roll", "Skill"], [77, "Luck Be a Robot", "Skill"],
      [78, "A Blur of Fingers and Brass", "Skill"], [79, "Ride to Ruin", "Skill"], [80, "Devil's Tine Red", "Skill"], [81, "Hot Hand", "Skill"],
      [82, "Stand and Bleed", "Skill"], [83, "Shootist", "Skill"], [84, "Hard-Boiled", "Skill"], [85, "Your Huckleberry", "Skill"],
      [88, "Unleashed", "Skill"], [89, "Wretched Shadows", "Skill"], [90, "Devil's Tine Blue", "Skill"], [91, "Late Scratch", "Skill"],
      [92, "Trick-Taker", "Skill"], [93, "Sounds of Rain", "Skill"], [94, "Go for Broke", "Skill"], [95, "Alchemy", "Skill"],
      [96, "Splash the pot", "Skill"], [97, "Insurance", "Skill"], [98, "Fast Hands", "Skill"], [99, "Riding High", "Skill"],
      [100, "Bonemeal Ticket", "Skill"], [101, "Before She Knows You're Dead", "Skill"], [102, "Luckless", "Skill"], [103, "Ready to Roll", "Skill"],
      [104, "Red Moon Rising", "Skill"], [105, "O Fortuna", "Skill"], [106, "Charm Bracelet", "Skill"], [108, "Sweet Roll", "Skill"],
      [109, "Luck Be a Robot", "Skill"], [110, "A Blur of Fingers and Brass", "Skill"], [111, "Ride to Ruin", "Skill"], [112, "Devil's Tine Red", "Skill"],
      [113, "Hot Hand", "Skill"], [114, "Stand and Bleed", "Skill"], [115, "Shootist", "Skill"], [116, "Hard-Boiled", "Skill"],
      [117, "Your Huckleberry", "Skill"], [120, "Unleashed", "Skill"], [121, "Wretched Shadows", "Skill"], [122, "Devil's Tine Blue", "Skill"],
      [123, "Late Scratch", "Skill"], [124, "Trick-Taker", "Skill"], [125, "Sounds of Rain", "Skill"], [126, "Go for Broke", "Skill"],
      [127, "Alchemy", "Skill"], [128, "Splash the pot", "Skill"], [129, "Insurance", "Skill"], [130, "Fast Hands", "Skill"],
      [131, "Riding High", "Skill"], [132, "Bonemeal Ticket", "Skill"], [133, "Before She Knows You're Dead", "Skill"], [134, "Luckless", "Skill"],
      [135, "Ready to Roll", "Skill"], [136, "Red Moon Rising", "Skill"], [137, "O Fortuna", "Skill"], [138, "Charm Bracelet", "Skill"],
      [140, "Sweet Roll", "Skill"], [141, "Luck Be a Robot", "Skill"], [142, "A Blur of Fingers and Brass", "Skill"], [143, "Ride to Ruin", "Skill"],
      [144, "Devil's Tine Red", "Skill"], [145, "Hot Hand", "Skill"], [146, "Stand and Bleed", "Skill"], [147, "Shootist", "Skill"],
      [148, "Hard-Boiled", "Skill"], [149, "Your Huckleberry", "Skill"], [152, "Unleashed", "Skill"], [153, "Wretched Shadows", "Skill"],
      [154, "Devil's Tine Blue", "Skill"], [155, "Late Scratch", "Skill"], [156, "Trick-Taker", "Skill"], [157, "Sounds of Rain", "Skill"],
      [158, "Go for Broke", "Skill"], [159, "Alchemy", "Skill"], [160, "Splash the pot", "Skill"], [161, "Insurance", "Skill"],
      [162, "Fast Hands", "Skill"], [163, "Riding High", "Skill"], [164, "Bonemeal Ticket", "Skill"], [165, "Before She Knows You're Dead", "Skill"],
      [166, "Luckless", "Skill"], [167, "Ready to Roll", "Skill"], [168, "Red Moon Rising", "Skill"], [169, "O Fortuna", "Skill"],
      [170, "Charm Bracelet", "Skill"], [172, "Sweet Roll", "Skill"], [173, "Luck Be a Robot", "Skill"], [174, "A Blur of Fingers and Brass", "Skill"],
      [175, "Ride to Ruin", "Skill"], [176, "Devil's Tine Red", "Skill"], [177, "Hot Hand", "Skill"], [178, "Stand and Bleed", "Skill"],
      [179, "Shootist", "Skill"], [180, "Hard-Boiled", "Skill"], [181, "Your Huckleberry", "Skill"], [184, "Unleashed", "Skill"],
      [185, "Wretched Shadows", "Skill"], [186, "Devil's Tine Blue", "Skill"], [187, "Late Scratch", "Skill"], [188, "Trick-Taker", "Skill"],
      [189, "Sounds of Rain", "Skill"], [190, "Go for Broke", "Skill"], [191, "Alchemy", "Skill"], [192, "Splash the pot", "Skill"],
      [193, "Insurance", "Skill"], [194, "Fast Hands", "Skill"], [195, "Riding High", "Skill"], [196, "Bonemeal Ticket", "Skill"],
      [197, "Before She Knows You're Dead", "Skill"], [198, "Luckless", "Skill"], [199, "Ready to Roll", "Skill"], [200, "Red Moon Rising", "Skill"],
      [201, "O Fortuna", "Skill"], [202, "Charm Bracelet", "Skill"], [204, "Sweet Roll", "Skill"], [205, "Luck Be a Robot", "Skill"],
      [206, "A Blur of Fingers and Brass", "Skill"], [207, "Ride to Ruin", "Skill"], [208, "Devil's Tine Red", "Skill"], [209, "Hot Hand", "Skill"],
      [210, "Stand and Bleed", "Skill"], [211, "Shootist", "Skill"], [212, "Hard-Boiled", "Skill"], [214, "Your Huckleberry", "Skill"],
      [216, "Unleashed", "Skill"], [222, "Gamer", "Name+Skin+Leg Effect"], [223, "Can't Stop Winning", "Skill"], [224, "Turn of Fate", "Skill"],
      [225, "High Stakes", "Skill"], [227, "Fortune's Favor", "Skill"], [228, "Let it Ride", "Skill"], [229, "The Wilds", "Skill"],
      [230, "Potent Posse", "Skill"], [231, "Restless Remains", "Skill"], [232, "Sorcerer", "Skill"], [233, "Tooth of Nail", "Skill"],
      [234, "Serendipity", "Skill"], [235, "Sidekick's Revenge", "Skill"], [236, "The Glorious Dead", "Skill"], [237, "Accursed Bones", "Skill"],
      [238, "Tormented", "Skill"], [240, "Graveyard Shift", "Skill"], [242, "Snake Eyes", "Skill"], [243, "Call", "Skill"],
      [244, "Brimstone", "Skill"], [245, "Fast C4SH", "Skill"], [246, "Firestorm", "Skill"], [247, "Burn the House Down", "Skill"],
      [248, "High Noon", "Skill"], [249, "Bloodstained Moon", "Skill"], [251, "Lawless", "Skill"], [252, "Truck Full of Nitro", "Skill"],
      [254, "War Wagon", "Skill"], [255, "Pale Rider", "Skill"], [256, "Nothing Beats Lead", "Skill"], [258, "Mr. Pocket", "Skill"],
      [259, "Unshaken", "Skill"], [260, "From Gloam to Glow", "Skill"], [262, "Dusty Trail", "Skill"], [264, "Bleed the Bad", "Skill"],
      [265, "High Roller", "Skill"], [266, "Take the Pot", "Skill"], [267, "Stack the Deck", "Skill"], [268, "Legerdamain", "Skill"],
      [269, "Vigorish", "Skill"], [270, "Dealer's Bluff", "Skill"], [272, "Ace in the Hole", "Skill"], [273, "Around the Corner", "Skill"],
      [275, "House Edge", "Skill"], [276, "C4SH Game", "Skill"], [277, "No Limit", "Skill"], [278, "Ante Up", "Skill"],
      [279, "Kill Button", "Skill"], [280, "Payout", "Skill"], [281, "Boom or Bust", "Skill"], [282, "Tender Hearts", "Skill"],
      [283, "Card Sharp", "Skill"], [284, "Hot Streak", "Skill"], [286, "Can't Stop Winning", "Skill"], [287, "Turn of Fate", "Skill"],
      [288, "High Stakes", "Skill"], [290, "Fortune's Favor", "Skill"], [291, "Let it Ride", "Skill"], [292, "The Wilds", "Skill"],
      [293, "Potent Posse", "Skill"], [294, "Restless Remains", "Skill"], [295, "Sorcerer", "Skill"], [296, "Tooth of Nail", "Skill"],
      [297, "Serendipity", "Skill"], [298, "Sidekick's Revenge", "Skill"], [299, "The Glorious Dead", "Skill"], [300, "Accursed Bones", "Skill"],
      [301, "Tormented", "Skill"], [303, "Graveyard Shift", "Skill"], [305, "Snake Eyes", "Skill"], [306, "Call", "Skill"],
      [307, "Brimstone", "Skill"], [308, "Fast C4SH", "Skill"], [309, "Firestorm", "Skill"], [310, "Burn the House Down", "Skill"],
      [311, "High Noon", "Skill"], [312, "Bloodstained Moon", "Skill"], [314, "Lawless", "Skill"], [315, "Truck Full of Nitro", "Skill"],
      [317, "War Wagon", "Skill"], [318, "Pale Rider", "Skill"], [319, "Nothing Beats Lead", "Skill"], [321, "Mr. Pocket", "Skill"],
      [322, "Unshaken", "Skill"], [323, "From Gloam to Glow", "Skill"], [325, "Dusty Trail", "Skill"], [327, "Bleed the Bad", "Skill"],
      [328, "High Roller", "Skill"], [329, "Take the Pot", "Skill"], [330, "Stack the Deck", "Skill"], [331, "Legerdamain", "Skill"],
      [332, "Vigorish", "Skill"], [333, "Dealer's Bluff", "Skill"], [335, "Ace in the Hole", "Skill"], [336, "Around the Corner", "Skill"],
      [338, "House Edge", "Skill"], [339, "C4SH Game", "Skill"], [340, "No Limit", "Skill"], [341, "Ante Up", "Skill"],
      [342, "Kill Button", "Skill"], [343, "Payout", "Skill"], [344, "Boom or Bust", "Skill"], [345, "Tender Hearts", "Skill"],
      [346, "Card Sharp", "Skill"], [347, "Hot Streak", "Skill"], [349, "Can't Stop Winning", "Skill"], [350, "Turn of Fate", "Skill"],
      [351, "High Stakes", "Skill"], [353, "Fortune's Favor", "Skill"], [354, "Let it Ride", "Skill"], [355, "The Wilds", "Skill"],
      [356, "Potent Posse", "Skill"], [357, "Restless Remains", "Skill"], [358, "Sorcerer", "Skill"], [359, "Tooth of Nail", "Skill"],
      [360, "Serendipity", "Skill"], [361, "Sidekick's Revenge", "Skill"], [362, "The Glorious Dead", "Skill"], [363, "Accursed Bones", "Skill"],
      [364, "Tormented", "Skill"], [366, "Graveyard Shift", "Skill"], [368, "Snake Eyes", "Skill"], [369, "Call", "Skill"],
      [370, "Brimstone", "Skill"], [371, "Fast C4SH", "Skill"], [372, "Firestorm", "Skill"], [373, "Burn the House Down", "Skill"],
      [374, "High Noon", "Skill"], [375, "Bloodstained Moon", "Skill"], [377, "Lawless", "Skill"], [378, "Truck Full of Nitro", "Skill"],
      [380, "War Wagon", "Skill"], [381, "Pale Rider", "Skill"], [382, "Nothing Beats Lead", "Skill"], [384, "Mr. Pocket", "Skill"],
      [385, "Unshaken", "Skill"], [386, "From Gloam to Glow", "Skill"], [388, "Dusty Trail", "Skill"], [390, "Bleed the Bad", "Skill"],
      [391, "High Roller", "Skill"], [392, "Take the Pot", "Skill"], [393, "Stack the Deck", "Skill"], [394, "Legerdamain", "Skill"],
      [395, "Vigorish", "Skill"], [396, "Dealer's Bluff", "Skill"], [398, "Ace in the Hole", "Skill"], [399, "Around the Corner", "Skill"],
      [401, "House Edge", "Skill"], [402, "C4SH Game", "Skill"], [403, "No Limit", "Skill"], [404, "Ante Up", "Skill"],
      [405, "Kill Button", "Skill"], [406, "Payout", "Skill"], [407, "Boom or Bust", "Skill"], [408, "Tender Hearts", "Skill"],
      [409, "Card Sharp", "Skill"], [410, "Hot Streak", "Skill"], [412, "Can't Stop Winning", "Skill"], [413, "Turn of Fate", "Skill"],
      [414, "High Stakes", "Skill"], [416, "Fortune's Favor", "Skill"], [417, "Let it Ride", "Skill"], [418, "The Wilds", "Skill"],
      [419, "Potent Posse", "Skill"], [420, "Restless Remains", "Skill"], [421, "Sorcerer", "Skill"], [422, "Tooth of Nail", "Skill"],
      [423, "Serendipity", "Skill"], [424, "Sidekick's Revenge", "Skill"], [425, "The Glorious Dead", "Skill"], [426, "Accursed Bones", "Skill"],
      [427, "Tormented", "Skill"], [429, "Graveyard Shift", "Skill"], [431, "Snake Eyes", "Skill"], [432, "Call", "Skill"],
      [433, "Brimstone", "Skill"], [434, "Fast C4SH", "Skill"], [435, "Firestorm", "Skill"], [436, "Burn the House Down", "Skill"],
      [437, "High Noon", "Skill"], [438, "Bloodstained Moon", "Skill"], [440, "Lawless", "Skill"], [441, "Truck Full of Nitro", "Skill"],
      [443, "War Wagon", "Skill"], [444, "Pale Rider", "Skill"], [445, "Nothing Beats Lead", "Skill"], [447, "Mr. Pocket", "Skill"],
      [448, "Unshaken", "Skill"], [449, "From Gloam to Glow", "Skill"], [451, "Dusty Trail", "Skill"], [453, "Bleed the Bad", "Skill"],
      [454, "High Roller", "Skill"], [455, "Take the Pot", "Skill"], [456, "Stack the Deck", "Skill"], [457, "Legerdamain", "Skill"],
      [458, "Vigorish", "Skill"], [459, "Dealer's Bluff", "Skill"], [461, "Ace in the Hole", "Skill"], [462, "Around the Corner", "Skill"],
      [464, "House Edge", "Skill"], [465, "C4SH Game", "Skill"], [466, "No Limit", "Skill"], [467, "Ante Up", "Skill"],
      [468, "Kill Button", "Skill"], [469, "Payout", "Skill"], [470, "Boom or Bust", "Skill"], [471, "Tender Hearts", "Skill"],
      [472, "Card Sharp", "Skill"], [473, "Hot Streak", "Skill"], [475, "Can't Stop Winning", "Skill"], [476, "Turn of Fate", "Skill"],
      [477, "High Stakes", "Skill"], [479, "Fortune's Favor", "Skill"], [480, "Let it Ride", "Skill"], [481, "The Wilds", "Skill"],
      [482, "Potent Posse", "Skill"], [483, "Restless Remains", "Skill"], [484, "Sorcerer", "Skill"], [485, "Tooth of Nail", "Skill"],
      [486, "Serendipity", "Skill"], [487, "Sidekick's Revenge", "Skill"], [488, "The Glorious Dead", "Skill"], [489, "Accursed Bones", "Skill"],
      [490, "Tormented", "Skill"], [492, "Graveyard Shift", "Skill"], [494, "Snake Eyes", "Skill"], [495, "Call", "Skill"],
      [496, "Brimstone", "Skill"], [497, "Fast C4SH", "Skill"], [498, "Firestorm", "Skill"], [499, "Burn the House Down", "Skill"],
      [500, "High Noon", "Skill"], [501, "Bloodstained Moon", "Skill"], [503, "Lawless", "Skill"], [504, "Truck Full of Nitro", "Skill"],
      [506, "War Wagon", "Skill"], [507, "Pale Rider", "Skill"], [508, "Nothing Beats Lead", "Skill"], [510, "Mr. Pocket", "Skill"],
      [511, "Unshaken", "Skill"], [512, "From Gloam to Glow", "Skill"], [514, "Dusty Trail", "Skill"], [516, "Bleed the Bad", "Skill"],
      [517, "High Roller", "Skill"], [518, "Take the Pot", "Skill"], [519, "Stack the Deck", "Skill"], [520, "Legerdamain", "Skill"],
      [521, "Vigorish", "Skill"], [522, "Dealer's Bluff", "Skill"], [524, "Ace in the Hole", "Skill"], [525, "Around the Corner", "Skill"],
      [527, "House Edge", "Skill"], [528, "C4SH Game", "Skill"], [529, "No Limit", "Skill"], [530, "Ante Up", "Skill"],
      [531, "Kill Button", "Skill"], [532, "Payout", "Skill"], [533, "Boom or Bust", "Skill"], [534, "Tender Hearts", "Skill"],
      [535, "Card Sharp", "Skill"], [536, "Hot Streak", "Skill"], [538, "Hooligan", "Name+Skin+Leg Effect"],
      [543, "Prestidigitator", "Name+Skin+Leg Effect"], [545, "Trainer", "Name+Skin+Leg Effect"]
    ],
    /* Loveless (Corpohacker / family 402): names from Nexus inv_name_part np_cm_corpo_*. */
    loveless: [
      [51, "Keylogger", "Name+Skin"], [15, "Hacktivist", "Name+Skin"], [14, "Researcher", "Name+Skin"],
      [13, "Assimilator", "Name+Skin"], [12, "Royal We", "Name+Skin"], [11, "Wyrmkind", "Name+Skin"],
      [10, "Defragger", "Name+Skin"], [9, "Corrupter", "Name+Skin"], [8, "Eminence", "Name+Skin"],
      [7, "System", "Name+Skin"],
      [6, "Devourer", "Name+Skin+Leg Effect"], [5, "Virophile", "Name+Skin+Leg Effect"],
      [4, "Montage Maker", "Name+Skin+Leg Effect"], [3, "Memory Hoarder", "Name+Skin+Leg Effect"],
      [2, "Trackstar", "Name+Skin+Leg Effect"], [1, "Functional Human", "Name+Skin+Leg Effect"],
      [540, "Martyr", "Name+Skin+Leg Effect"], [545, "Programmer", "Name+Skin+Leg Effect"],
      [539, "Boomer", "Name+Skin+Leg Effect"], [538, "Plague Engineer", "Name+Skin+Leg Effect"],
      [222, "Puppetmaster", "Name+Skin+Leg Effect"]
    ]
  };
  Object.keys(extras).forEach(function (key) {
    var target = Array.isArray(root[key]) ? root[key].slice() : [];
    var seen = new Set(target.map(function (row) { return JSON.stringify(row); }));
    var seenIdKind = new Set(target.map(function (row) {
      return Array.isArray(row) ? String(row[0]) + '|' + String(row[2] || '') : '';
    }));
    (extras[key] || []).forEach(function (row) {
      if (!Array.isArray(row) || row.length < 2) return;
      var sig = JSON.stringify(row);
      if (seen.has(sig)) return;
      var idKind = String(row[0]) + '|' + String(row[2] || '');
      if (seenIdKind.has(idKind)) return;
      seen.add(sig);
      seenIdKind.add(idKind);
      target.push(row);
    });
    root[key] = target;
  });
})();
