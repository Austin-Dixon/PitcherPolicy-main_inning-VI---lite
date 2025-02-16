"""Module that defines our Pitch classes"""
from re import T
from typing import List, Dict
from pathlib import Path
import numpy as np
import json

from tensorflow.keras import models

from pitches.zone import Zone
from pitches.pitch_zone_enums import BallZoneNames, PitchNames, StrikeZoneNames
from pitches.obvious_zones import ObviousZones
from pitches.zones import Zones
from pitches.pitch import Pitch
from pitches.error_dist import NormalErrorDistribution

from state_action_enums import Outcomes, CountStates, BatActs
from state import Count, Inning, nxt
import copy

# Load models
take_model = models.load_model("../models/take_2015-2018.h5")
swing_trans_model = models.load_model("../models/transition_model_2015-2018.h5")
acc_model = models.load_model("../models/error_2015-2018.h5")

# Load pitcher tensors
with open("./tensors/pitcher_tensors.json") as f:
    pitcher_tensors = json.load(f)

# load batter tensors
with open("./tensors/batter_tensors.json") as f:
    batter_tensors = json.load(f)

# defining the absolute path to our swing_trans matrix
REL_PATH = "../data_cleaning/combining_data/swing_transitions.json"
NN_REL_PATH = "./trans_prob_mat.json"
SWING_TRANS_PATH = Path(__file__).parent / REL_PATH
NN_SWING_TRANS_PATH = Path(__file__).parent / NN_REL_PATH

# defining strike and obvious zone dimensions
LEFT_X = -0.831
MID_LEFT_X = -0.277
MID_RIGHT_X = 0.277
RIGHT_X = 0.831

TOP_Y = 1.074
MID_TOP_Y = 0.358
MID_BOT_Y = -0.358
BOT_Y = -1.074

# dimensions of our strike zones
STRIKE_HEIGHT = TOP_Y - MID_TOP_Y
STRIKE_WIDTH = RIGHT_X - MID_RIGHT_X

s_zone_inputs = {
    StrikeZoneNames.ZERO.value: {
        "coords": (LEFT_X, MID_TOP_Y),
        "height": STRIKE_HEIGHT,
        "width": STRIKE_WIDTH,
    },
    StrikeZoneNames.ONE.value: {
        "coords": (MID_LEFT_X, MID_TOP_Y),
        "height": STRIKE_HEIGHT,
        "width": STRIKE_WIDTH,
    },
    StrikeZoneNames.TWO.value: {
        "coords": (MID_RIGHT_X, MID_TOP_Y),
        "height": STRIKE_HEIGHT,
        "width": STRIKE_WIDTH,
    },
    StrikeZoneNames.THREE.value: {
        "coords": (LEFT_X, MID_BOT_Y),
        "height": STRIKE_HEIGHT,
        "width": STRIKE_WIDTH,
    },
    StrikeZoneNames.FOUR.value: {
        "coords": (MID_LEFT_X, MID_BOT_Y),
        "height": STRIKE_HEIGHT,
        "width": STRIKE_WIDTH,
    },
    StrikeZoneNames.FIVE.value: {
        "coords": (MID_RIGHT_X, MID_BOT_Y),
        "height": STRIKE_HEIGHT,
        "width": STRIKE_WIDTH,
    },
    StrikeZoneNames.SIX.value: {
        "coords": (LEFT_X, BOT_Y),
        "height": STRIKE_HEIGHT,
        "width": STRIKE_WIDTH,
    },
    StrikeZoneNames.SEVEN.value: {
        "coords": (MID_LEFT_X, BOT_Y),
        "height": STRIKE_HEIGHT,
        "width": STRIKE_WIDTH,
    },
    StrikeZoneNames.EIGHT.value: {
        "coords": (MID_RIGHT_X, BOT_Y),
        "height": STRIKE_HEIGHT,
        "width": STRIKE_WIDTH,
    },
}

cutoffs = {
    PitchNames.FOUR_SEAM.value: {
        BallZoneNames.NINE.value: (-1.2, 1.4),
        BallZoneNames.TEN.value: (None, 1.5),
        BallZoneNames.ELEVEN.value: (None, None),
        BallZoneNames.TWELVE.value: (-1.5, None),
        BallZoneNames.THIRTEEN.value: (1.4, None),
        BallZoneNames.FOURTEEN.value: (None, None),
        BallZoneNames.FIFTEEN.value: (None, -1.25),
        BallZoneNames.SIXTEEN.value: (None, None),
    },
    PitchNames.TWO_SEAM.value: {
        BallZoneNames.NINE.value: (-1.3, 1.4),
        BallZoneNames.TEN.value: (None, 1.2),
        BallZoneNames.ELEVEN.value: (None, None),
        BallZoneNames.TWELVE.value: (-1.5, None),
        BallZoneNames.THIRTEEN.value: (1.2, None),
        BallZoneNames.FOURTEEN.value: (-1.2, -1.4),
        BallZoneNames.FIFTEEN.value: (None, -1.5),
        BallZoneNames.SIXTEEN.value: (None, None),
    },
    PitchNames.CUTTER.value: {
        BallZoneNames.NINE.value: (None, None),
        BallZoneNames.TEN.value: (None, 1.2),
        BallZoneNames.ELEVEN.value: (None, None),
        BallZoneNames.TWELVE.value: (-1.5, 0.8),
        BallZoneNames.THIRTEEN.value: (1.6, 0.8),
        BallZoneNames.FOURTEEN.value: (-1.5, -1.8),
        BallZoneNames.FIFTEEN.value: (None, -1.9),
        BallZoneNames.SIXTEEN.value: (1.5, -1.8),
    },
    PitchNames.SLIDER.value: {
        BallZoneNames.NINE.value: (None, None),
        BallZoneNames.TEN.value: (None, 1.2),
        BallZoneNames.ELEVEN.value: (None, None),
        BallZoneNames.TWELVE.value: (-1.4, 0.6),
        BallZoneNames.THIRTEEN.value: (1.5, 0.6),
        BallZoneNames.FOURTEEN.value: (-1.6, -2.1),
        BallZoneNames.FIFTEEN.value: (None, -2.1),
        BallZoneNames.SIXTEEN.value: (1.5, -2.2),
    },
    PitchNames.CURVE.value: {
        BallZoneNames.NINE.value: (None, None),
        BallZoneNames.TEN.value: (None, None),
        BallZoneNames.ELEVEN.value: (None, None),
        BallZoneNames.TWELVE.value: (-1.4, 0.5),
        BallZoneNames.THIRTEEN.value: (1.5, 0.5),
        BallZoneNames.FOURTEEN.value: (-1.3, -2.1),
        BallZoneNames.FIFTEEN.value: (None, -2.4),
        BallZoneNames.SIXTEEN.value: (1.3, -2.0),
    },
    PitchNames.CHANGEUP.value: {
        BallZoneNames.NINE.value: (None, None),
        BallZoneNames.TEN.value: (None, None),
        BallZoneNames.ELEVEN.value: (None, None),
        BallZoneNames.TWELVE.value: (-1.4, 0.9),
        BallZoneNames.THIRTEEN.value: (1.5, 0.9),
        BallZoneNames.FOURTEEN.value: (-1.4, -1.8),
        BallZoneNames.FIFTEEN.value: (None, -1.8),
        BallZoneNames.SIXTEEN.value: (1.4, -1.9),
    },
}

norm_err_dist = {
    PitchNames.FOUR_SEAM.value: NormalErrorDistribution(0.18, 0.24),
    PitchNames.TWO_SEAM.value: NormalErrorDistribution(0.24, 0.26),
    PitchNames.CUTTER.value: NormalErrorDistribution(0.21, 0.34),
    PitchNames.SLIDER.value: NormalErrorDistribution(0.23, 0.39),
    PitchNames.CURVE.value: NormalErrorDistribution(0.21, 0.48),
    PitchNames.CHANGEUP.value: NormalErrorDistribution(0.15, 0.25),
}


def gen_pitches() -> Dict[str, Pitch]:
    """Instantiates all of our Pitch objects
    (by instantiating zone, obvious_zones, and zones)

    Returns
    -------
    List[Pitch]
        a list of all our Pitch objects
    """
    pitches: Dict[str, Pitch] = {}

    # these remain the same for all pitches
    o_zones = ObviousZones(LEFT_X, BOT_Y)
    s_zones = list()
    for name, val in s_zone_inputs.items():
        s_zones.append(Zone(name, val["coords"], val["width"], val["height"]))

    for p_name, p_cutoffs in cutoffs.items():
        b_zones = list()
        for z_name, z_cuts in p_cutoffs.items():
            if z_cuts != (None, None):

                if z_name == BallZoneNames.NINE.value:
                    coords = (z_cuts[0], TOP_Y)
                    width = LEFT_X - z_cuts[0]
                    height = z_cuts[1] - TOP_Y
                    b_zones.append(Zone(z_name, coords, width, height))

                elif z_name == BallZoneNames.TWELVE.value:
                    coords = (z_cuts[0], BOT_Y)
                    width = LEFT_X - z_cuts[0]
                    height = 2 * TOP_Y if z_cuts[1] is None else z_cuts[1] + TOP_Y
                    b_zones.append(Zone(z_name, coords, width, height))

                elif z_name == BallZoneNames.TEN.value:
                    coords = (LEFT_X, TOP_Y)
                    width = 2 * RIGHT_X
                    height = z_cuts[1] - TOP_Y
                    b_zones.append(Zone(z_name, coords, width, height))

                elif z_name == BallZoneNames.ELEVEN.value:
                    coords = (RIGHT_X, TOP_Y)
                    width = z_cuts[0] - RIGHT_X
                    height = z_cuts[1] - TOP_Y
                    b_zones.append(Zone(z_name, coords, width, height))

                elif z_name == BallZoneNames.THIRTEEN.value:
                    coords = (RIGHT_X, BOT_Y)
                    width = z_cuts[0] - RIGHT_X
                    height = 2 * TOP_Y if z_cuts[1] is None else z_cuts[1] + TOP_Y
                    b_zones.append(Zone(z_name, coords, width, height))

                elif z_name == BallZoneNames.FIFTEEN.value:
                    coords = (LEFT_X, z_cuts[1])
                    width = 2 * RIGHT_X
                    height = BOT_Y - z_cuts[1]
                    b_zones.append(Zone(z_name, coords, width, height))

                elif z_name == BallZoneNames.SIXTEEN.value:
                    coords = (RIGHT_X, z_cuts[1])
                    width = z_cuts[0] - RIGHT_X
                    height = BOT_Y - z_cuts[1]
                    b_zones.append(Zone(z_name, coords, width, height))

                elif z_name == BallZoneNames.FOURTEEN.value:
                    coords = (z_cuts[0], z_cuts[1])
                    width = LEFT_X - z_cuts[0]
                    height = BOT_Y - z_cuts[1]
                    b_zones.append(Zone(z_name, coords, width, height))

        zones = Zones(s_zones, b_zones, o_zones)
        pitches[p_name] = Pitch(p_name, zones, norm_err_dist[p_name])

    return pitches


def gen_counts() -> List[Count]:
    """Instantiates all of our Count state objects

    Returns
    -------
    List[Count]
        a list of all our Count state objects
    """
    return [Count(Outcomes, int(c.value[0]), int(c.value[1])) for c in CountStates]

def gen_take_mat(model, batter_tensor, pitches, p_take_threshold=.2):
    """Generates a take matrix for all non-obvious zones

    Parameters
    ----------
    batter_id : int
        id of batter in at-bat
    pitches : Pitches
        pitches object representing all pitches
    p_take_threshold : float
        threshold at which a zone can be considered a taking zone based on the batters probability to swing
    

    Returns
    -------
    dict
        One-hot encoded dictionary for if a given non-obvious zone can be considered a take "
    """

    batch_batter_tensor = []
    batch_s_count_tensor = []
    batch_b_count_tensor = []
    batch_pitch_tensor = []

    #model trained on non-obvious zones


    for pitch_type in pitches:
        for zone in range(9,17):
            pitch_tensor = get_pitch_matrix(zone, pitch_type)
            for s_count in range(3):
                for b_count in range(4):
                        batch_pitch_tensor.append(pitch_tensor)
                        batch_batter_tensor.append(batter_tensor)
                        batch_s_count_tensor.append(s_count)
                        batch_b_count_tensor.append(b_count)


    batch_pitch_tensor = np.array(batch_pitch_tensor)
    batch_batter_tensor = np.array(batch_batter_tensor)
    batch_s_count_tensor = np.array(batch_s_count_tensor)
    batch_b_count_tensor = np.array(batch_b_count_tensor)  

    predictions = model.predict(
    [
        batch_batter_tensor,
        batch_s_count_tensor,
        batch_b_count_tensor,
        batch_pitch_tensor,
    ]
    )

    prediction_index = 0
    take_mat = {}

    for pitch_type in pitches:
        take_mat[pitch_type] = {}
       
        for zone in range(9,17):
            zone_key = str(zone)+"a"
            pitch_tensor = get_pitch_matrix(zone, pitch_type)
            take_mat[pitch_type][zone_key] = {}
          
            for s_count in range(3):
                for b_count in range(4):
                    count_key = str(b_count)+str(s_count)
                    swing_prob = predictions[prediction_index][0]
                    prediction_index+=1

                    if swing_prob<p_take_threshold:
                        take_mat[pitch_type][zone_key][count_key] = True
                    else:
                        take_mat[pitch_type][zone_key][count_key] = False
  
    return take_mat

def gen_swing_trans_matrix(model, pitcher_tensor, batter_tensor, take_mat, pitches):
    """Generates swing transition matrix indexed by pitch type and count for a given pitcher/batter combination


    Parameters
    ----------
    pitcher_id : int
        id of pitcher in at-bat
    batter_id : int
        id of batter in at-bat
    take_mat : dict
        dict mapping a ball zone for each pitch type and count to a take zone (1) or not (0)
    pitches : Pitches
        pitches object representing all pitches
    
    
    Returns
    _______
    dict
        a transition matrix dict to index [pitch_type][pitch_zone][count] = [prob_strike,prob_foul,prob_out,prob_hit]
    """
    batch_pitch_tensor = []
    batch_pitcher_tensor = []
    batch_batter_tensor = []
    batch_s_count_tensor = []
    batch_b_count_tensor = []



    # iterate over list of pitch types
    for pitch_type in pitches.keys():
        # iterate over zones
        zone_list_raw = pitches[pitch_type].zones.strike_zones + pitches[pitch_type].zones.ball_zones
        zone_list = []
        for zone in zone_list_raw:
            zone_list.append(zone.name)
        zone_list = zone_list + ["9b","10b","11b","12b","13b","14b","15b","16b"]
       
        for zone in zone_list:

            # generate pitch matrix
            pitch_tensor = get_pitch_matrix(int(zone[:-1]), pitch_type)
            # iterate over s_count
            for s_count in range(3):
                for b_count in range(4):
                    zone_take = False
                    
                    str_count = str(b_count) + str(s_count)
                    if zone in take_mat[pitch_type].keys():
                        zone_take = take_mat[pitch_type][zone][str_count]


                    # generate prediction from model
                    if zone[-1] == "b" or zone_take:
                        continue
                    else:
                        batch_pitch_tensor.append(pitch_tensor)
                        batch_pitcher_tensor.append(pitcher_tensor)
                        batch_batter_tensor.append(batter_tensor)
                        batch_s_count_tensor.append(s_count)
                        batch_b_count_tensor.append(b_count)


    batch_pitch_tensor = np.array(batch_pitch_tensor)
    batch_pitcher_tensor = np.array(batch_pitcher_tensor)
    batch_batter_tensor = np.array(batch_batter_tensor)
    batch_s_count_tensor = np.array(batch_s_count_tensor)
    batch_b_count_tensor = np.array(batch_b_count_tensor)  


    predictions = model.predict(
    [
        batch_pitcher_tensor,
        batch_batter_tensor,
        batch_s_count_tensor,
        batch_b_count_tensor,
        batch_pitch_tensor,
    ]
    )

        # instantiate the dict
    swing_transition_matrix = {}

    prediction_index = 0
    # iterate over list of pitch types
    for pitch_type in pitches.keys():
        # iterate over zones
        swing_transition_matrix[pitch_type] = {}
        zone_list_raw = pitches[pitch_type].zones.strike_zones + pitches[pitch_type].zones.ball_zones
        zone_list = []
        for zone in zone_list_raw:
            zone_list.append(zone.name)
        zone_list = zone_list + ["9b","10b","11b","12b","13b","14b","15b","16b"]
       
        for zone in zone_list:
            # iterate over s_count
            swing_transition_matrix[pitch_type][zone] = {}
            for s_count in range(3):
                for b_count in range(4):
                    zone_take = False
                    str_count = str(b_count) + str(s_count)
                    if zone in take_mat[pitch_type].keys():
                        zone_take = take_mat[pitch_type][zone][str_count]


                    # generate prediction from model
                    if zone[-1] == "b" or zone_take:
                        swing_transition_matrix[pitch_type][zone][
                                str_count
                        ] = {Outcomes.BALL.value:1}
                    else:
                        prediction = predictions[prediction_index]
                        prediction_index+=1
                        cleaned_prediction = {
                            Outcomes.OUT.value: float(prediction[2]),
                            Outcomes.SINGLE.value: float(prediction[3]),
                            Outcomes.DOUBLE.value: float(prediction[4]),
                            Outcomes.TRIPLE.value: float(prediction[5]),
                            Outcomes.HOMERUN.value: float(prediction[6]),
                            Outcomes.FOUL.value: float(prediction[1]),
                            Outcomes.STRIKE.value: float(prediction[0]),
                        }
                        swing_transition_matrix[pitch_type][zone][
                            str_count
                        ] = cleaned_prediction
    return swing_transition_matrix

def get_pitch_matrix(zone, pitch_type):
    """Generates 5x5x6 array representing a one-hot encoding of pitch type/location


    Parameters
    ----------
    zone : int
        the zone number for a given pitch (zones in the range [0-16])
    pitch_type : str
        string representing the type of pitch thrown

    Returns
    -------
    array
        numpy array with the pitch type/zone one-hot encoded
    
    """
    
    pitch_types = ["FF", "FT", "CU", "CH", "FC", "SL"]
    pitch_tensor = np.zeros((5, 5, 6))
    p_ind = pitch_types.index(pitch_type)

    # (x,y)
    zone_index_map = {
        0: (1, 1),
        1: (2, 1),
        2: (3, 1),
        3: (1, 2),
        4: (2, 2),
        5: (3, 2),
        6: (1, 3),
        7: (2, 3),
        8: (3, 3),
        9: (0, 0),
        10: (np.s_[1:4], 0),
        11: (4, 0),
        12: (0, np.s_[1:4]),
        13: (4, np.s_[1:4]),
        14: (0, 4),
        15: (np.s_[1:4], 4),
        16: (4, 4),
    }
    pitch_tensor[zone_index_map[zone][0], zone_index_map[zone][1], p_ind] = 1

    return pitch_tensor


def gen_acc_mat(model, pitcher, pitches: Dict[str, Pitch]) -> dict:
    """Generates accuracy matrix by running error simulation for each pitch

    Parameters
    ----------
    pitches : Dict[str, Pitch]
        the list pitches a pitcher may throw

    Returns
    -------
    dict
        an accuracy matrix dict to index [pitch][int_zone][act_zone] = %in_act_zone
    """

    acc_mat = {}
    for p_name, pitch in pitches.items():
        acc_mat[p_name] = pitch.run_error_simulation_from_pitcher(model, pitcher)

    return acc_mat



def gen_trans_prob_mat(swing_trans_mat: dict, acc_mat: dict, take_mat:dict) -> dict:
    """Generates tansition probability matrix

    Parameters
    ----------
    swing_trans_mat : dict
        dict that defines the probability of an outcome (foul, swing, out, hit, ball)
        access probs by swing_trans_mat[pitch][zone][outcome] = %outcome
    acc_mat : dict
        dict that defines the accuracy matrix dict[pitch][int_zone][act_zone] = %in_act
    take_mat : dict
        dict mapping a ball zone for each pitch type and count to a take zone (1) or not (0)
    Returns
    -------
    dict
        a trans_prob_mat that contains the transition probabilities across all outcomes
        for a given pitcher and batter action; trans_prob_mat[pitch][zone][count][swing] = outcome probs
    """
    trans_prob_mat = {}

    for pitch in swing_trans_mat.keys():
        trans_prob_mat[pitch] = {}

        for int_zone in swing_trans_mat[pitch].keys():
            trans_prob_mat[pitch][int_zone] = {}

            for count in swing_trans_mat[pitch][int_zone].keys():
                
                zone_take = False
                if int_zone in take_mat[pitch].keys():
                    zone_take = take_mat[pitch][int_zone][count]


                trans_prob_mat[pitch][int_zone][count] = {
                    BatActs.TAKE.value: {
                        Outcomes.STRIKE.value: 0,
                        Outcomes.BALL.value: 0,
                    },
                    BatActs.SWING.value: {
                        Outcomes.OUT.value: 0,
                        Outcomes.SINGLE.value: 0,
                        Outcomes.DOUBLE.value: 0,
                        Outcomes.TRIPLE.value: 0,
                        Outcomes.HOMERUN.value: 0,
                        Outcomes.FOUL.value: 0,
                        Outcomes.STRIKE.value: 0,
                        Outcomes.BALL.value: 0,
                    },
                }
                if int_zone[-1] == "b" or zone_take:
                    trans_prob_mat[pitch][int_zone][count][BatActs.TAKE.value][
                        Outcomes.BALL.value
                    ] = 1
                if int_zone in acc_mat[pitch]:

                    for s_zone in [s.value for s in StrikeZoneNames]:
                        if s_zone in acc_mat[pitch][int_zone]:
                            trans_prob_mat[pitch][int_zone][count][BatActs.TAKE.value][
                                Outcomes.STRIKE.value
                            ] += acc_mat[pitch][int_zone][s_zone]

                    trans_prob_mat[pitch][int_zone][count][BatActs.TAKE.value][
                        Outcomes.BALL.value
                    ] = (
                        1
                        - trans_prob_mat[pitch][int_zone][count][BatActs.TAKE.value][
                            Outcomes.STRIKE.value
                        ]
                    )

                    for act_zone, prob_in_zone in acc_mat[pitch][int_zone].items():
                      
                        for outcome, prob_outcome in swing_trans_mat[pitch][act_zone][
                            count
                        ].items():
                            trans_prob_mat[pitch][int_zone][count][BatActs.SWING.value][
                                outcome
                            ] += (prob_in_zone * prob_outcome)
                else:
                    trans_prob_mat[pitch][int_zone][count][
                        BatActs.SWING.value
                    ] = swing_trans_mat[pitch][int_zone][count]

    return trans_prob_mat

def gen_inning_states(n): #n represents the max number of runs to terminate the game
    # NONE=(0,0,0,0,0,0,0,0,0)
    # #generate all possible Inning game states (with absolute order)
    # b=(1,0,0,0,0,0,0,0,0)
    # bs=[]
    # for i in range(9):
    #     bs.append(b)
    #     b=nxt(b)

    # #Alternative iteral brute force establishment of states    
    # states=[]
    # for b in bs:
    #     for b1 in range(2):
    #         for b2 in range(2):
    #             for b3 in range(2):
    #                 for ball in range(4):
    #                     for strike in range(3):
    #                         for run in range(n):
    #                             for out in range(3):
    #                                 states.append(Inning(b,{1:b1,2:b2,3:b3},{"balls":ball,"strikes":strike,"runs":run,"outs":out},n))
    # for i in range(n+1):
    #     states.append(Inning(NONE,{1:0,2:0,3:0},{"balls":0,"strikes":0,"runs":i,"outs":3},n))
    ACTIONS=("strike","foul","ball","out","single","double","triple","home run")
    states=[]
    stack=[Inning((1,0,0,0,0,0,0,0,0),{1:0,2:0,3:0},{"balls":0,"strikes":0,"runs":0,"outs":0},n)]
    while len(stack)>0:
        cur=stack[0]
        if cur not in states:
            states.append(cur)
            for act in ACTIONS:
                suc=cur.get_successor(act)
                if suc not in stack and suc not in states:
                    stack.append(suc)
        stack.remove(cur)
    return states

def gen_trans_inning_mat(pid,team):
    
    NONE=(0,0,0,0,0,0,0,0,0)
    pitcher=pitcher_tensors[pid]
    batters={}

    #storage of take zones and transition probabilities for each batter
    takes={}
    transitions={}

    #generate pitch types and possible count states
    pitches = gen_pitches()

    #generare accurracy matrix for selected pitcher
    acc_mat = gen_acc_mat(acc_model, pitcher, pitches)

    #generate batting team, map to positions, and transition probabilities for each batter
    for i in range(9):
        bid=list(NONE)
        bid[i]=1
        bid=tuple(bid)
        batters[bid]= batter_tensors[team[i]]
        take_mat = gen_take_mat(take_model, batters[bid], pitches, .2)
        nn_swing_trans_mat = gen_swing_trans_matrix(swing_trans_model, pitcher, batters[bid], take_mat, pitches)
        nn_trans_prob_mat = gen_trans_prob_mat(nn_swing_trans_mat, acc_mat, take_mat)
        takes[bid]=take_mat
        transitions[bid]=nn_trans_prob_mat

    #generate entry for terminal states with no probability of transitioning
    transitions[NONE]=copy.deepcopy(transitions[(1,0,0,0,0,0,0,0,0)])
    for pitch in transitions[NONE]:
        for zone in transitions[NONE][pitch]:
            for count in transitions[NONE][pitch][zone]:
                for batact in transitions[NONE][pitch][zone][count]:
                    for res in transitions[NONE][pitch][zone][count][batact]:
                        transitions[NONE][pitch][zone][count][batact][res]=0
    return transitions
