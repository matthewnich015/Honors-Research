# SCOPE: run all the functions created in the other scripts

import Calculate_ADU_Counts
import Calculate_Characteristics
import Calculate_Results_Statistics

Calculate_ADU_Counts.SetDataPathsToSmallTest()
#Calculate_ADU_Counts.Step0()
#Calculate_ADU_Counts.Step1()
Calculate_ADU_Counts.Step2()

# Calculate_ADU_Counts.ADUCheckTest()