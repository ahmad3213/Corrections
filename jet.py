import os
import ROOT
from .CorrectionsCore import *
# https://docs.google.com/spreadsheets/d/1JZfk78_9SD225bcUuTWVo4i02vwI5FfeVKH-dwzUdhM/edit#gid=1345121349

# MET corrections
# https://twiki.cern.ch/twiki/bin/viewauth/CMS/MissingETRun2Corrections
# https://lathomas.web.cern.ch/lathomas/METStuff/XYCorrections/XYMETCorrection_withUL17andUL18andUL16.h
# https://indico.cern.ch/event/1033432/contributions/4339934/attachments/2235168/3788215/metxycorrections_UL2016.pdf
# JEC uncertainty sources took from recommendation here:
# https://twiki.cern.ch/twiki/bin/view/CMS/JECDataMC
# https://github.com/cms-jet/JECDatabase/tree/master
# https://twiki.cern.ch/twiki/bin/view/CMS/JECUncertaintySources
# JER uncertainty source took from:
# https://twiki.cern.ch/twiki/bin/view/CMS/JetResolution
# https://github.com/cms-jet/JRDatabase
# smearing procedure
# https://twiki.cern.ch/twiki/bin/viewauth/CMS/JetResolution#Smearing_procedures

# according to recommendation, SummerUL19 should be used but also SummerUL20 are available for JER.
'''BBEC1_2016postVFP

IMPORTANT
From: https://twiki.cern.ch/twiki/bin/view/CMS/PdmVRun2LegacyAnalysis

Note: The RunIISummer19UL16(APV) samples have a bug in the beamspot position affecting only (most of the) 2016 samples HN, HN, talk. The RunIISummer19UL16 samples will be invalidated at the end of August. Please migrate to Summer20UL now. All Summer19UL samples are based on an older version of pythia. The difference of Summer19UL and Summer20UL due to the difference in the pythia version was studied and found negligible 1 2 3. Invalidation and deletion of all RunIISummer19 samples, for all years, is scheduled for the end of September 2021

'''


directories_JER = {
    "2018_UL":"Summer19UL18_JRV2",
    "2017_UL": "Summer19UL17_JRV2",
    "2016preVFP_UL":"Summer20UL16APV_JRV3",
    "2016postVFP_UL":"Summer20UL16_JRV3",
    }
directories_JEC = {
    "2018_UL":"Summer19UL18_V5_MC",
    "2017_UL": "Summer19UL17_V5_MC",
    "2016preVFP_UL":"Summer19UL16APV_V7_MC",
    "2016postVFP_UL":"Summer19UL16_V7_MC",
    }

regrouped_files_names = {
    "2018_UL":"RegroupedV2_Summer19UL18_V5_MC_UncertaintySources_AK4PFchs.txt",
    "2017_UL": "RegroupedV2_Summer19UL17_V5_MC_UncertaintySources_AK4PFchs.txt",
    "2016preVFP_UL":"RegroupedV2_Summer19UL16APV_V7_MC_UncertaintySources_AK4PFchs.txt",
    "2016postVFP_UL":"RegroupedV2_Summer19UL16_V7_MC_UncertaintySources_AK4PFchs.txt"
    }


class JetCorrProducer:
    JEC_SF_path = 'Corrections/data/JME/{}'
    jsonPath_btag = "/cvmfs/cms.cern.ch/rsync/cms-nanoAOD/jsonpog-integration/POG/BTV/{}/btagging.json.gz"

    initialized = False

    jet_algorithm = "AK4PFPuppi"

    uncSources_regrouped = [ "FlavorQCD",
                             "RelativeBal",
                             "HF",
                             "BBEC1",
                             "EC2",
                             "Absolute",
                             "BBEC1_",
                             "Absolute_",
                             "EC2_",
                             "HF_",
                             "RelativeSample_" ]

    uncSources_minimal = ["Total"]

    jet_jsonPath = "/cvmfs/cms.cern.ch/rsync/cms-nanoAOD/jsonpog-integration/POG/JME/{}/jet_jerc.json.gz"
    # fatjet_jsonPath = "/cvmfs/cms.cern.ch/rsync/cms-nanoAOD/jsonpog-integration/POG/JME/{}/fatJet_jerc.json.gz"
    jersmear_jsonPath = "/cvmfs/cms.cern.ch/rsync/cms-nanoAOD/jsonpog-integration/POG/JME/jer_smear.json.gz"

    # maps period to JER tag (only for MC!)
    jer_tag_map = { "2022_Summer22": "Summer22_22Sep2023_JRV1_MC",
                    "2022_Prompt": "JR_Winter22Run3_V1_MC",
                    "2022_Summer22EE": "Summer22EE_22Sep2023_JRV1_MC",
                    "2023_Summer23BPix": "Summer23BPixPrompt23_RunD_JRV1_MC",
                    "2023_Summer23": "Summer23Prompt23_RunCv1234_JRV1_MC" }

    # maps period to JEC tag
    jec_tag_map_mc = { "2022_Summer22": "Summer22_22Sep2023_V2_MC",
                       "2022_Prompt": "Winter22Run3_V2_MC",
                       "2022_Summer22EE": "Summer22EE_22Sep2023_V2_MC",
                       "2023_Summer23BPix": "Summer23BPixPrompt23_V1_MC",
                       "2023_Summer23": "Summer23Prompt23_V1_MC" }

    # maps period to base tag
    # for DATA: jec_tag = {base_tag}_Run{letters}_V{version}_DATA
    jec_tag_map_data = { "2022_Summer22": "Summer22_22Sep2023_Run{}_V2_DATA",
                         "2023_Summer23BPix": "Summer23BPixPrompt23_Run{}_V2_DATA",
                         "2022_Prompt": "Winter22Run3_Run{}_V2_DATA",
                         "2023_Summer23": "Summer23Prompt23_Run{}_V1_DATA",
                         "2022_Summer22EE": "Summer22EE_22Sep2023_Run{}_V2_DATA" }

    run_versions = {"2022_Summer22": [],
                    "2023_Summer23BPix": [],
                    "2022_Prompt": [],
                    "2023_Summer23": ["v123", "v4"],
                    "2022_Summer22EE": [],
                    "2024_Winter24": []}

    run_letters = {"2022_Summer22": ["CD"],
                   "2023_Summer23BPix": ["D"],
                   "2022_Prompt": ["C", "D"],
                   "2023_Summer23": ["C"],
                   "2022_Summer22EE": ["E", "F", "G"],
                   "2024_Winter24": ["BCD", "E", "F", "G", "H"]}

    #Sources = []
    period = None
    def __init__(self, period, isData, sample_name, use_corrlib = True, use_regrouped = False):
        self.isData = isData
        self.sample_name = sample_name
        self.use_regrouped = use_regrouped
        self.use_corrlib = use_corrlib
        self.uncSources_toUse = []
        if self.use_regrouped:
            self.uncSources_toUse = JetCorrProducer.uncSources_regrouped
        else:
            self.uncSources_toUse = JetCorrProducer.uncSources_minimal
        self.year = int(period[:4])
        print(f"period: {period}")
        print(f"year: {self.year}")
        if not self.use_corrlib:
            print("Initializing old JetCorrProducer")
            JEC_SF_path_period = JetCorrProducer.JEC_SF_path.format(period)
            JEC_dir = directories_JEC[period]
            JEC_SF_db = "Corrections/data/JECDatabase/textFiles/"

            JER_dir = directories_JER[period]
            JER_SF_db = "Corrections/data/JRDatabase/textFiles/"

            JER_SF_txtPath_MC = f"{JER_SF_db}/{JER_dir}_MC/{JER_dir}_MC_SF_AK4PFchs.txt"
            JER_PtRes_txtPath_MC = f"{JER_SF_db}/{JER_dir}_MC/{JER_dir}_MC_PtResolution_AK4PFchs.txt"
            JER_PhiRes_txtPath_MC = f"{JER_SF_db}/{JER_dir}_MC/{JER_dir}_MC_PhiResolution_AK4PFchs.txt"
            JER_EtaRes_txtPath_MC = f"{JER_SF_db}/{JER_dir}_MC/{JER_dir}_MC_EtaResolution_AK4PFchs.txt"

            JER_SF_txtPath_data = f"{JER_SF_db}/{JER_dir}_DATA/{JER_dir}_DATA_SF_AK4PFchs.txt"
            JER_PtRes_txtPath_data = f"{JER_SF_db}/{JER_dir}_DATA/{JER_dir}_DATA_PtResolution_AK4PFchs.txt"
            JER_PhiRes_txtPath_data = f"{JER_SF_db}/{JER_dir}_DATA/{JER_dir}_DATA_PhiResolution_AK4PFchs.txt"
            JER_EtaRes_txtPath_data = f"{JER_SF_db}/{JER_dir}_DATA/{JER_dir}_DATA_EtaResolution_AK4PFchs.txt"

            JEC_Regouped_txtPath_MC = f"{JEC_SF_db}/{JEC_dir}/{regrouped_files_names[period]}"

            ptResolution = os.path.join(os.environ['ANALYSIS_PATH'],JER_PtRes_txtPath_MC.format(period))
            ptResolutionSF = os.path.join(os.environ['ANALYSIS_PATH'],JER_SF_txtPath_MC.format(period))
            JEC_Regrouped = os.path.join(os.environ['ANALYSIS_PATH'], JEC_Regouped_txtPath_MC.format(period))
            if self.isData:
                ptResolution = os.path.join(os.environ['ANALYSIS_PATH'],JER_PtRes_txtPath_data.format(period))
                ptResolutionSF = os.path.join(os.environ['ANALYSIS_PATH'],JER_SF_txtPath_data.format(period))
            if not JetCorrProducer.initialized:
                ROOT.gSystem.Load("libJetMETCorrectionsModules.so")
                ROOT.gSystem.Load("libCondFormatsJetMETObjects.so")
                ROOT.gSystem.Load("libCommonToolsUtils.so")
                headers_dir = os.path.dirname(os.path.abspath(__file__))
                header_path = os.path.join(headers_dir, "jet.h")
                JME_calc_base = os.path.join(headers_dir, "JMECalculatorBase.cc")
                JME_calc_path = os.path.join(headers_dir, "JMESystematicsCalculators.cc")
                ROOT.gInterpreter.Declare(f'#include "{JME_calc_base}"')
                ROOT.gInterpreter.Declare(f'#include "{JME_calc_path}"')
                ROOT.gInterpreter.Declare(f'#include "{header_path}"')
                ROOT.gInterpreter.ProcessLine(f"""::correction::JetCorrProvider::Initialize("{ptResolution}", "{ptResolutionSF}","{JEC_Regrouped}", "{periods[period]}")""")
                JetCorrProducer.period = period
                JetCorrProducer.initialized = True
        else:
            print("Initializing new JetCorrProducer")
            jet_path = JetCorrProducer.jet_jsonPath.format(period)
            jet_jsonFile = os.path.join(os.environ['ANALYSIS_PATH'], jet_path)
            jersmear_path = JetCorrProducer.jersmear_jsonPath
            jetsmear_jsonFile = os.path.join(os.environ['ANALYSIS_PATH'], jersmear_path)

            year = period.split('_')[0]
            jec_tag_map = JetCorrProducer.jec_tag_map_data if self.isData else JetCorrProducer.jec_tag_map_mc
            jec_tag = jec_tag_map[period]
            if self.isData:
                letter_list = JetCorrProducer.run_letters[period]
                version_list = JetCorrProducer.run_versions[period]

                sample_letter = ""
                sample_version = ""
                if sample_name[-1].isalpha():
                    sample_letter = sample_name[-1]
                elif sample_name[-1].isnumeric():
                    tokens = sample_name.split('_')
                    sample_version = tokens[-1]
                    sample_letter = tokens[-2][-1]

                # in some cases, sample letter can be compound:
                # e.g. for 2022_Summer22 run letter is CD
                # if there is no exact match, take compound letter
                if sample_letter not in letter_list:
                    matches = [let for let in letter_list if sample_letter in let]
                    if len(matches) != 1:
                        raise RuntimeError(f"ambiguous deduction of sample letter for {sample_name}: got letter options {matches}")
                    sample_letter = matches[0]

                # same for run version:
                # e.g. for 2023_Summer23 run version is v123 or v4
                # if there is no exact match, take compound version
                if version_list and sample_version not in version_list:
                    matches = [v for v in version_list if sample_version in v]
                    if len(matches) != 1:
                        raise RuntimeError(f"ambiguous deduction of sample version for {sample_name}: got version options {matches}")
                    sample_version = matches[0]

                letters = sample_letter + sample_version
                if not sample_letter and not sample_version:
                    raise RuntimeError(f"sample name {sample_name} doesn't follow expected pattern base_letter_version")
                jec_tag = jec_tag.format(letters)

            jer_tag = JetCorrProducer.jer_tag_map[period]
            algo = JetCorrProducer.jet_algorithm

            if not JetCorrProducer.initialized:
                headers_dir = os.path.dirname(os.path.abspath(__file__))
                header_path = os.path.join(headers_dir, "jet.h")
                ROOT.gInterpreter.Declare(f'#include "{header_path}"')
                is_data = "true" if self.isData else "false"
                regrouped = "true" if self.use_regrouped else "false"
                apply_compound = "true"
                ROOT.gInterpreter.ProcessLine(f"""::correction::JetCorrectionProvider::Initialize("{jet_jsonFile}",
                                                                                                  "{jetsmear_jsonFile}",
                                                                                                  "{jec_tag}",
                                                                                                  "{jer_tag}",
                                                                                                  "{algo}",
                                                                                                  "{year}",
                                                                                                   {is_data},
                                                                                                   {regrouped},
                                                                                                   {apply_compound})""")
                JetCorrProducer.initialized = True


    def getP4Variations(self, df, source_dict, apply_JER, apply_JES):
        class_name = ""
        if self.use_corrlib:
            apply_jer = "true" if apply_JER and not self.isData else "false"
            if not self.isData:
                df = df.Define("Jet_p4_shifted_map", f'''::correction::JetCorrectionProvider::getGlobal().getShiftedP4(Jet_pt, Jet_eta, Jet_phi, Jet_mass,
                                                                                                                       Jet_rawFactor, Jet_area, Rho_fixedGridRhoFastjetAll, event, {apply_jer},
                                                                                                                       GenJet_pt, Jet_genJetIdx)''')
            else:
                df = df.Define("Jet_p4_shifted_map", f'''::correction::JetCorrectionProvider::getGlobal().getShiftedP4(Jet_pt, Jet_eta, Jet_phi, Jet_mass,
                                                                                                                       Jet_rawFactor, Jet_area, Rho_fixedGridRhoFastjetAll, event, {apply_jer})''')
            class_name = "JetCorrectionProvider"
        else:
            df = df.Define('Jet_p4_shifted_map', f'''::correction::JetCorrProvider::getGlobal().getShiftedP4(
                            Jet_pt, Jet_eta, Jet_phi, Jet_mass, Jet_rawFactor, Jet_area,
                            Jet_jetId, Rho_fixedGridRhoFastjetAll, Jet_partonFlavour, 0, GenJet_pt, GenJet_eta,
                            GenJet_phi, GenJet_mass, event)''')
            class_name = "JetCorrProvider"

        apply_jer_list = []
        if apply_JER:
            apply_jer_list.append("JER")
        apply_jes_list = self.uncSources_toUse if apply_JES else []
        # central variable is imported from CorrectionsCore.py, where it is defined
        for source in [ central ] + apply_jes_list + apply_jer_list:
            source_eff = source
            if source in apply_jes_list: # source!=central and source != "JER":
                source_eff = "JES_" + source_eff
            if source.endswith("_") :
                source_eff = source_eff + JetCorrProducer.period.split("_")[0]
                source += "year"
            updateSourceDict(source_dict, source_eff, 'Jet')
            for scale in getScales(source):
                syst_name = getSystName(source_eff, scale)
                df = df.Define(f"Jet_p4_{syst_name}", f"Jet_p4_shifted_map.at({{::correction::{class_name}::UncSource::{source}, ::correction::UncScale::{scale}}})")
                df = df.Define(f"Jet_p4_{syst_name}_delta", f"Jet_p4_{syst_name} - Jet_p4_{nano}")

        return df, source_dict


    def getEnergyResolution(self, df):
        if self.use_corrlib:
            df = df.Define("Jet_ptRes", "::correction::JetCorrectionProvider::getGlobal().GetResolutions(Jet_pt, Jet_mass, Jet_rawFactor, Jet_eta, Rho_fixedGridRhoFastjetAll)")
        else:
            df = df.Define("Jet_ptRes", "::correction::JetCorrProvider::getGlobal().getResolution(Jet_pt, Jet_eta, Rho_fixedGridRhoFastjetAll)")
        return df

    #def getVetoMap(self, df):
    #    df = df.Define(f"vetoMapLooseRegion", "Jet_pt > 15 && ( Jet_jetId & 2 ) && (Jet_puId > 0 || Jet_pt >50) ")

    # jet pT > 15 GeV
    # tight jet ID
    # PU jet ID for CHS jets with pT < 50 GeV
    # jet EM fraction (charged + neutral) < 0.9
    # jets that don’t overlap with PF muon (dR < 0.2) RemoveOverlaps(Jet_p4, vetoMapLooseRegion, Muon_p4, Muon_p4.size(), 0.2)