# SCOPE: runs the calculations to determine the amount of ADUs allowed for each combination of variables

import math
import random
import pandas as pd
import geopandas as gpd
import shapely
import pathlib
import itertools

# === GLOBAL VARIABLES =================================================================================================
# full area data paths (38,683 parcels)]
pF, bF = "../Data/Parcel_Polygons/REA_Property_Polygons.shp", "../Data/Building_Polygons/Building_Polygons.shp"
sF, zF = "../Data/Street_Network/Street_Network.shp", "../Data/Zoning_Polygons/Zoning_Polygons.shp"
fF, dF = "../Data/FEMA_Flood_Zone_Polygons/FEMA_Flood_Zone_Polygons.shp", "../Data/Driveway_Polygons/Driveway_Polygons.shp"
hF, tF = "../Data/Zoning_Historic_District_Polygons/Zoning_Historic_District_Polygons.shp", "../Data/Tree_Canopy/Tree_Canopy_2023.shp"
# large test data paths (4,159 parcels)
pL, bL = "../Data/Parcel_Polygons_Large/Parcel_Polygons_Large.shp", "../Data/Building_Polygons_Large/Building_Polygons_Large.shp"
sL, zL = "../Data/Street_Network_Large/Street_Network_Large.shp", "../Data/Zoning_Polygons_Large/Zoning_Polygons_Large.shp"
fL, dL = "../Data/FEMA_Flood_Zone_Polygons_Large/FEMA_Flood_Zone_Polygons_Large.shp", "../Data/Driveway_Polygons_Large/Driveway_Polygons_Large.shp"
hL, tL = "../Data/Zoning_Historic_District_Polygons_Large/Zoning_Historic_District_Polygons_Large.shp", "../Data/Tree_Canopy/Tree_Canopy_2023.shp"
# small test area data paths (339 parcels)
pS, bS = "../Data/Parcel_Polygons_Small/Parcel_Polygons_Small.shp", "../Data/Building_Polygons_Small/Building_Polygons_Small.shp"
sS, zS = "../Data/Street_Network_Small/Street_Network_Small.shp", "../Data/Zoning_Polygons_Small/Zoning_Polygons_Small.shp"
fS, dS = "../Data/FEMA_Flood_Zone_Polygons_Small/FEMA_Flood_Zone_Polygons_Small.shp", "../Data/Driveway_Polygons_Small/Driveway_Polygons_Small.shp"
hS, tS = "../Data/Zoning_Historic_District_Polygons_Small/Zoning_Historic_District_Polygons_Small.shp", "../Data/Tree_Canopy/Tree_Canopy_2023.shp"
# master data paths (default full area, change to test cases via functions)
(parcelsPath, buildingFootprintPath, streetNetworkPath, zoningPath, floodplainsPath,
 historicDistrictsPath, drivewaysPath, treeCanopyPath) = pF, bF, sF, zF, fF, hF, dF, tF

# === PRIVATE FUNCTIONS ================================================================================================
# set test cases
def SetDataPathsToLargeTest():
    global parcelsPath, buildingFootprintsPath, streetNetworkPath, zoningPath, floodplainsPath, historicDistrictsPath, drivewaysPath
    (parcelsPath, buildingFootprintsPath, streetNetworkPath, zoningPath, floodplainsPath,
     historicDistrictsPath, drivewaysPath, treeCanopyPath) = pL, bL, sL, zL, fL, hL, dL, tL

def SetDataPathsToSmallTest():
    global parcelsPath, buildingFootprintsPath, streetNetworkPath, zoningPath, floodplainsPath, historicDistrictsPath, drivewaysPath
    (parcelsPath, buildingFootprintsPath, streetNetworkPath, zoningPath, floodplainsPath,
     historicDistrictsPath, drivewaysPath, treeCanopyPath) = pS, bS, sS, zS, fS, hS, dS, tS


# step 1 functions
def CalculateSetbacks(fullParcel: gpd.GeoDataFrame, parcel: gpd.GeoDataFrame, setback: int):
    # do a negative buffer to get the new full parcel with setback
    fullParcelSetback = fullParcel.copy()
    fullParcelSetback["geometry"] = fullParcel.buffer(-setback)
    # get only the part of the parcel that is inside the new setback full polygon
    parcelSetbackSeries = parcel.geometry.intersection(fullParcelSetback.geometry)
    parcelSetbacks = gpd.GeoDataFrame(geometry=parcelSetbackSeries, crs="EPSG:2283")
    return parcelSetbacks

def CalculateLotCoverage(fullParcel: gpd.GeoDataFrame, buildingArea: float):
    buildingFootprints = gpd.read_file("../Data/Building_Polygons/Building_Polygons.shp")

    # find the area of buildings in the parcel
    spatialIndex = buildingFootprints.sindex
    fullParcel["buildings"] = [buildingFootprints.iloc[spatialIndex.query(p, predicate="intersects")].
    intersection(p).union_all() for p in fullParcel.geometry]
    fullParcel["areaExisting"] = gpd.GeoSeries(fullParcel["buildings"]).area

    # calculate lot coverage
    fullParcel["totalArea"] = fullParcel["areaExisting"] + buildingArea
    fullParcel["lotCoverage"] = fullParcel["totalArea"] / fullParcel.geometry.area
    return fullParcel

def CalculateFAR(fullParcel: gpd.GeoDataFrame, buildingArea: float):
    buildingFootprints = gpd.read_file("../Data/Building_Polygons/Building_Polygons.shp")

    # find the area of buildings in the parcel
    spatialIndex = buildingFootprints.sindex
    fullParcel["buildings"] = [buildingFootprints.iloc[spatialIndex.query(p, predicate="intersects")].
    intersection(p).union_all() for p in fullParcel.geometry]
    fullParcel["areaExisting"] = gpd.GeoSeries(fullParcel["buildings"]).area

    # calculate FAR (using 2.5 as average number of floors for pre-existing buildings)
    fullParcel["totalArea"] = fullParcel["areaExisting"] * 2.5 + buildingArea
    fullParcel["FAR"] = fullParcel["totalArea"] / fullParcel.geometry.area
    return fullParcel


# ADU checks
# checks if an ADU can fit in a parcel. Can only check for one ADU, not multiple, and only checks for detatched
def ADUCheckBasic(buildableArea: shapely.Polygon):
    # check overall square feet
    if buildableArea.area < 190:
        return False
    else:
        # create 2 polygons to test if they fit (square case and long case, general approximation for all cases)
        ADU1 = shapely.Polygon([(0, 0), (13.79, 0), (13.79, 13.79), (0, 13.79)])
        ADU2 = shapely.Polygon([(0, 0), (7, 0), (7, 27.15), (0, 27.15)])
        ADUSizes = [ADU1, ADU2]
        # find centroid, bounding box, and radius in both directions of polygon
        centroid = buildableArea.centroid
        minX, minY, maxX, maxY = buildableArea.bounds
        radiusX = abs(maxX - minX) / 2
        radiusY = abs(maxY - minY) / 2

        # run optimization polygon containment method on both ADU sizes to see if they fit
        fits = False
        for ADU in ADUSizes:
            if fits:
                break
            # set defaults
            vars = {1: centroid.x + random.randrange((-int(radiusX)), (int(radiusX))),
                    2: centroid.y + random.randrange((-int(radiusY)), (int(radiusY))),
                    3: 90} # vars are: posX, posY, rot
            varsLast = vars.copy() # vars are: posX, posY, rot
            score = 0
            scoreLast = 0

            # try 10 times to get it inside the polygon by placing randomly, this will get most cases very quickly
            options = {}
            for i in range(0, 10):
                vars = {1: centroid.x + random.randrange((-int(radiusX)), (int(radiusX))),
                        2: centroid.y + random.randrange((-int(radiusY)), (int(radiusY))),
                        3: 90}  # vars are: posX, posY, rot
                ADUT = shapely.affinity.translate(ADU, xoff=vars[1], yoff=vars[2])
                ADUT = shapely.affinity.rotate(ADUT, vars[3])
                overlap = buildableArea.intersection(ADUT)
                score = overlap.area
                if score > 189.9:
                    fits = True
                    break
                options[str(i+1)] = (vars[1], vars[2], vars[3], score)

            # if that didn't work, assume it is a harder case and continue with the best 3 of 10
            if not fits:
                bestOptions = [options[str(1)], options[str(2)], options[str(3)]]
                for i in range(4, 11):
                    worstIndex = bestOptions.index(min(bestOptions, key=lambda k: k[3]))
                    if options[str(i)][3] > bestOptions[worstIndex][3]:
                        bestOptions[worstIndex] = options[str(i)]

                # for each of the best 3 of 10, run the optimization function
                for bestOption in bestOptions:
                    if not fits:
                        # set defaults
                        vars[1], vars[2], vars[3] = bestOption[0], bestOption[1], bestOption[2]
                        score = bestOption[3]

                        varsShift = {1: 1, 2: 1, 3: 1}  # vars are: posXDir, posYDir, rotDir
                        scoreMax = 0
                        currentVar = 1
                        beenHereBefore = 0
                        iteration = 1

                        while score < 189.9:
                            varsLast = vars.copy()
                            scoreLast = score

                            # shift variable
                            if currentVar == 3:
                                variableShift = varsShift[currentVar] * 30
                            else:
                                variableShift = varsShift[currentVar] * 30 * (1 - score / 190)
                            vars[currentVar] += variableShift

                            # evaulate new score
                            ADUT = shapely.affinity.translate(ADU, xoff=vars[1], yoff=vars[2])
                            ADUT = shapely.affinity.rotate(ADUT, vars[3])
                            overlap = buildableArea.intersection(ADUT)
                            score = overlap.area

                            # re-evaluate shift for next time based on results
                            if score - scoreLast > 0:
                                if vars[currentVar] - varsLast[currentVar] > 0:
                                    varsShift[currentVar] = 1 # if the shift helped and was positive, stay positive
                                else:
                                    varsShift[currentVar] = -1 # if the shift helped and was negative, stay negative
                            else:
                                if vars[currentVar] - varsLast[currentVar] > 0:
                                    varsShift[currentVar] = -1 # if the shift didn't help and was positive, change to negative
                                else:
                                    varsShift[currentVar] = 1 # if the shift didnt help and was negative, change to positive

                            # if score is 190, mark as fits
                            if score > 189.9:
                                fits = True
                                break

                            # if score equals max score and max score didnt change, iterate beenHereBefore
                            if score > scoreMax - 1 and score < scoreMax + 1:
                                beenHereBefore += 1
                            # adjust new max score
                            if score > scoreMax:
                                scoreMax = score
                            # if beenHereBefore equals 5 or iteration equals 10000, assume a loop and exit
                            iteration += 1
                            if beenHereBefore == 5 or iteration == 1000:
                                break

                            # change currentVar
                            if currentVar < 3:
                                currentVar += 1
                            else:
                                currentVar = 1
        if fits:
            # buildableArea = buildableArea.difference(ADUT) # cut out for testing
            return True
        else:
            return False

# checks if multiple ADUs can fit in a parcel and returns the number and type that can fit (detatched / attatched)
#def ADUCheckMultiUnit(buildableArea: Polygon, MaxUnits):


# misc. other
# use this to seperate the front and back yard of a parcel
def SplitFrontBackYard(parcel: shapely.Polygon):
    # load data
    driveways = gpd.read_file(drivewaysPath)
    buildingFootprints = gpd.read_file(buildingFootprintsPath)
    streetNetwork = gpd.read_file(streetNetworkPath)

    # find the bounding box polygon of the parcel and convert to edges
    bbox = parcel.minimum_rotated_rectangle
    coords = list(bbox.exterior.coords)
    edges = [shapely.LineString([coords[i], coords[i+1]]) for i in range(len(coords)-1)]
    bboxE = gpd.GeoDataFrame({"Edge_Type": None, "geometry": edges}, crs="EPSG:2283")

    # find the front of the bbox using the road centerline
    # create a buffer of the bbox and get only the road segments that intersect with that buffer
    buffer = bbox.buffer(100)
    nearbyStreets = gpd.clip(streetNetwork, buffer)
    # for each edge in the bbox
    fronts = gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:2283")
    if len(nearbyStreets) != 0:
        for idx, row in bboxE.iterrows():
            edge = row.geometry
            edgeCenter = edge.centroid
            # check if the edge is close enough to mark as front yard
            distance = min(edgeCenter.distance(nearbyStreets.geometry))
            if distance < 50:
                row = gpd.GeoDataFrame([{"geometry": bboxE.loc[idx, "geometry"]}], crs = "EPSG:2283")
                fronts = pd.concat([fronts, row], ignore_index=True)
    # if there are more than one front edge or no front edges, use the driveway to determine the correct front edge
    if len(fronts) != 1:
        fronts = fronts.iloc[0:0]
        clipped = gpd.clip(driveways, bbox)
        if len(clipped) > 0:
            driveway = shapely.union_all(clipped.geometry)
        else: driveway = None
        # if there is no driveway or nearby streets, choose an edge at random
        if driveway == None or len(nearbyStreets) == 0:
            row = gpd.GeoDataFrame([{"geometry": bboxE.loc[0, "geometry"]}], crs = "EPSG:2283")
            fronts = pd.concat([fronts, row], ignore_index=True)
        else:
            # find the closest street to the driveway
            nearbyStreets["distance"] = nearbyStreets.geometry.distance(driveway)
            closestStreetSegment = nearbyStreets.loc[nearbyStreets["distance"].idxmin()]
            # find the edge closest to the closest street
            distIdx = (10000, 0)
            for idx, row in bboxE.iterrows():
                edgeCenter = row.geometry.centroid
                distance = edgeCenter.distance(closestStreetSegment.geometry)
                if distance < distIdx[0]:
                    distIdx = (distance, idx)
            row = gpd.GeoDataFrame([{"geometry": bboxE.loc[distIdx[1], "geometry"]}], crs = "EPSG:2283")
            fronts = pd.concat([fronts, row], ignore_index=True)
    front = fronts.loc[0, "geometry"]

    # find all buildings in the parcel
    buildings = gpd.clip(buildingFootprints, bbox)
    # find the largest building (main house)
    if len(buildings) != 0:
        building = buildings.loc[buildings.geometry.area.idxmax()]
        # find the center point
        buildingCenter = building.geometry.centroid
    # if there are no buildings, the center point will be the parcel centroid
    else:
        buildingCenter = parcel.centroid

    # move the front edge to the center point
    coords = list(front.coords)
    offsetX = buildingCenter.x - coords[0][0]
    offsetY = buildingCenter.y - coords[0][1]
    yardSplit = shapely.affinity.translate(front, offsetX, offsetY)
    # expand the line in both directions
    coords = list(yardSplit.coords)
    direction = (coords[1][0] - coords[0][0], coords[1][1] - coords[0][1])
    newCoords = ([(coords[0][0] - direction[0], coords[0][1] - direction[1])] + coords +
                 [(coords[1][0] + direction[0], coords[1][1] + direction[1])])
    yardSplit = shapely.LineString(newCoords)

    # split the bounding box with the line
    split = shapely.ops.split(bbox, yardSplit)
    splitBox = list(split.geoms)
    # mark as front and back yard
    dist1 = splitBox[0].centroid.distance(front)
    dist2 = splitBox[1].centroid.distance(front)
    if dist1 < dist2:
        frontBox = splitBox[0]
        backBox = splitBox[1]
    else:
        frontBox = splitBox[1]
        backBox = splitBox[0]
    # use the split bounding box to split the parcel
    parcelGDF = gpd.GeoDataFrame(geometry=[parcel], crs = "EPSG:2283")
    frontYardGDF = gpd.clip(parcelGDF, frontBox)
    backYardGDF = gpd.clip(parcelGDF, backBox)
    return pd.Series({"Front_Yard": shapely.union_all(frontYardGDF.geometry), "Back_Yard": shapely.union_all(backYardGDF.geometry)})

# === STEP 0: SETUP ====================================================================================================
def Step0():
    print("STEP 0: Loading data")
    # Projected Coordinate System: NAD 1983 StatePlane Virginia North FIPS 4501 (US Feet)
    # Projection: Lambert Conformal Conic
    # WKID: 2283
    parcels = gpd.read_file(parcelsPath)
    zoning = gpd.read_file(zoningPath)
    floodplains = gpd.read_file(floodplainsPath)
    historicDistricts = gpd.read_file(historicDistrictsPath)
    buildingFootprints = gpd.read_file(buildingFootprintsPath)
    driveways = gpd.read_file(drivewaysPath)

    print("STEP 0: Removing parcels in non-residential zones, floodplains, or historic districts")
    # remove all parcels that are not residential zoned or are in a floodplain or historic district
    nonResidentialMask = ~zoning["ZN_DESIG"].str.contains("R-6|R-5|R-8|R-10|R-20|R15-30T|R-10T|R2-7|RA-H-3.2")
    nonResidential = zoning[nonResidentialMask]

    floodplains = floodplains[floodplains.geometry.is_valid]
    mask = floodplains["FLD_ZONE"].str.contains("A")
    floodplains = floodplains[mask]

    merged = gpd.GeoDataFrame(pd.concat([floodplains, historicDistricts, nonResidential]))
    mask = parcels.geometry.apply(lambda g: merged.intersects(g).any())
    filteredParcels = parcels[~mask]

    # add a column to parcels giving each parcel an id
    filteredParcels = filteredParcels.reset_index(drop=True)
    filteredParcels["Parcel_ID"] = filteredParcels.index

    # remove all building footprints that aren't in remaining parcels
    print("STEP 0: Removing all building footprints that aren't in remaining parcels")
    buildingFootprints = buildingFootprints[buildingFootprints.geometry.is_valid]
    filteredFootprints = buildingFootprints.overlay(filteredParcels, how="intersection")

    # cut building footprint and driveways out of remaining parcels
    print("STEP 0: Removing building footprints and driveways from parcels")
    merged = gpd.GeoDataFrame(pd.concat([filteredFootprints, driveways]))
    parcelStart = filteredParcels.overlay(merged, how="difference")

    # split front and back yard
    splitYards = filteredParcels.geometry.apply(SplitFrontBackYard).apply(pd.Series)
    frontYards = gpd.GeoDataFrame({"Parcel_ID": splitYards.index, "geometry": splitYards["Front_Yard"]}, crs="EPSG:2283")
    backYards = gpd.GeoDataFrame({"Parcel_ID": splitYards.index, "geometry": splitYards["Front_Yard"]}, crs="EPSG:2283")

    print("STEP 0: Saving results to file")
    filteredParcels.to_file("../Output/Full_Parcels.gpkg", driver="GPKG", layer="FullParcels")
    frontYards.to_file("../Output/Front_Yards.gpkg", driver="GPKG", layer="FrontYards")
    backYards.to_file("../Output/Back_Yards.gpkg", driver="GPKG", layer="BackYards")
    parcelStart.to_file("../Output/Step0_Parcels.gpkg", driver="GPKG", layer="ParcelStart")
    filteredFootprints.to_file("../Output/Step0_Building_Footprints.gpkg", driver="GPKG", layer="FilteredFootprints")


# === STEP 1: SETBACKS, LOT COVERAGE, AND FAR ==========================================================================
def Step1():
    print("STEP 1: Loading data")
    # Projected Coordinate System: NAD 1983 StatePlane Virginia North FIPS 4501 (US Feet)
    # Projection: Lambert Conformal Conic
    # WKID: 2283
    parcels = gpd.read_file("../Output/Step0_Parcels.gpkg", driver="GPKG", layer="ParcelStart")
    fullParcels = gpd.read_file("../Output/Full_Parcels.gpkg", driver="GPKG", layer="FullParcels")

    setbacks = [5, 10, 20, 30]
    FARs = [.3, .5, .7, .9]
    lotCoverages = [.2, .4, .6, .8]

    # Setbacks
    print("STEP 1: Calculating for setbacks")
    for setback in setbacks:
        print("STEP 1: Calculating Setback of " + str(setback) + " feet")
        parcelSetbacks = CalculateSetbacks(fullParcels, parcels, setback)
        result = parcelSetbacks.copy()
        result["Valid"] = parcelSetbacks.geometry.apply(ADUCheckBasic)
        mask = result["Valid"] == True
        result = result.loc[mask]
        result.to_file("../Output/S" + str(setback) + "/S" + str(setback) + ".gpkg")

    # Lot Coverage
    print("STEP 1: Calculating for lot coverages")
    for setback in setbacks:
        print("STEP 1: Calculating Lot Coverages for setback of " + str(setback) + " feet")
        base = gpd.read_file("../Output/S" + str(setback) + "/S" + str(setback) + ".gpkg")
        result = CalculateLotCoverage(base, 17.65)
        for lotCoverage in lotCoverages:
            result["Valid"] = result["lotCoverage"] > lotCoverage
            mask = result["Valid"] == True
            result = result.loc[mask]
            resultOutput = result.drop(columns=["lotCoverage", "totalArea", "areaExisting", "buildings"])
            resultOutput.to_file("../Output/S" + str(setback) + "/L" + str(int(lotCoverage * 100)) +
                           "/S" + str(setback) + "L" + str(int(lotCoverage * 100)) + ".gpkg")

    # FAR
    print("STEP 1: Calculating for FARs")
    for setback in setbacks:
        print("STEP 1: Calculating FARs for setback of " + str(setback) + " feet")
        base = gpd.read_file("../Output/S" + str(setback) + "/S" + str(setback) + ".gpkg")
        result = CalculateFAR(base, 17.65)
        for FAR in FARs:
            result["Valid"] = result["FAR"] > FAR
            mask = result["Valid"] == True
            result = result.loc[mask]
            resultOutput = result.drop(columns=["FAR", "totalArea", "areaExisting", "buildings"])
            resultOutput.to_file("../Output/S" + str(setback) + "/F" + str(FAR).replace("0", "") +
                           "/S" + str(setback) + "F" + str(FAR).replace("0", "") + ".gpkg")


# === STEP 2: HOUSING TYPE, TREE PRESERVATION, FRONT/BACK YARD, ADU TYPE, ADU NUMBER, PARKING ==========================
def Step2():
    print("STEP 2: Loading data")
    # Projected Coordinate System: NAD 1983 StatePlane Virginia North FIPS 4501 (US Feet)
    # Projection: Lambert Conformal Conic
    # WKID: 2283
    fullParcels = gpd.read_file("../Output/Full_Parcels.gpkg", driver="GPKG", layer="FullParcels")
    frontYards = gpd.read_file("../Output/Front_Yards.gpkg", driver="GPKG", layer="FrontYards")
    zoning = gpd.read_file(zoningPath)
    treeCanopy = gpd.read_file(treeCanopyPath)


    # lists of file path extensions
    setbacks = ["S5", "S10", "S20", "S30"]
    FARLCs = ["F.3", "F.5", "F.7", "F.9", "L20", "L40", "L60", "L80"]
    housingTypes = ["Single", "SingleMulti"]
    treePreservation = ["noTreePreservation", "TreePreservation"]
    frontBackYard = ["backOnly", "frontAndBack"]
    ADUType = "ADUType"
    ADUNumber = "ADUNumber"
    parking = ["noParkingRequired", "parkingRequired"]

    # housing type
    print ("Calculating for housing type")
    # split zoning for single family only
    singleMask = zoning["ZN_DESIG"].str.contains("R-6|R-5|R-8|R-10|R-20|R-10T")
    singleZoning = zoning[singleMask]
    for setback, FARLC in itertools.product(setbacks, FARLCs):
        path = ("../Output/" + setback + "/" + FARLC + "/")
        parcels = gpd.read_file(path + setback + FARLC + ".gpkg")
        for housingType in housingTypes:
            # create folder
            pathlib.Path(path + housingType).mkdir(parents=True, exist_ok=True)
            # if there are already no valid parcels or is single and multi family, make no changes
            if len(parcels.geometry) == 0 or housingType == "SingleMulti":
                output = parcels
            # else find single family only parcels
            else:
                mask = parcels.geometry.apply(lambda g: singleZoning.intersects(g).any())
                output = parcels[mask]
            # write to file
            output.to_file(path + housingType + "/" + setback + FARLC + housingType + ".gpkg", driver="GPKG")

    # tree preservation
    print ("Calculating for tree preservation")
    for setback, FARLC, housingType in itertools.product(setbacks, FARLCs, housingTypes):
        path = ("../Output/" + setback + "/" + FARLC + "/" + housingType + "/")
        parcels = gpd.read_file(path + setback + FARLC + housingType + ".gpkg")
        for treeOption in treePreservation:
            # create folder
            pathlib.Path(path + treeOption).mkdir(parents=True, exist_ok=True)
            # if there are already no valid parcels or is no tree preservation, make no changes
            if len(parcels.geometry) == 0 or treeOption == "noTreePreservation":
                output = parcels
            # else remove tree canopy from buildable area and re-assess
            else:
                parcelsNoTrees = gpd.overlay(parcels, treeCanopy, how="difference")
                parcelsNoTrees["Valid"] = parcelsNoTrees.geometry.apply(ADUCheckBasic)
                mask = parcelsNoTrees["Valid"] == True
                output = parcelsNoTrees.loc[mask]
            # write to file
            output.to_file(path + treeOption + "/" + setback + FARLC + housingType + treeOption + ".gpkg", driver="GPKG")

    # front / back yard
    print ("Calculating for back or front and back yard")
    for setback, FARLC, housingType, treeOption in itertools.product(setbacks, FARLCs, housingTypes, treePreservation):
        path = ("../Output/" + setback + "/" + FARLC + "/" + housingType + "/" + treeOption + "/")
        parcels = gpd.read_file(path + setback + FARLC + housingType + treeOption + ".gpkg")
        for yardOption in frontBackYard:
            # create folder
            pathlib.Path(path + yardOption).mkdir(parents=True, exist_ok=True)
            # if there are already no valid parcels or front and back yard, make no changes
            if len(parcels.geometry) == 0 or yardOption == "frontAndBack":
                output = parcels
            # else remove front yard from buildable area and re-assess
            else:
                parcelsBackyard = gpd.overlay(parcels, frontYards, how="difference")
                parcelsBackyard["Valid"] = parcelsBackyard.geometry.apply(ADUCheckBasic)
                mask = parcelsBackyard["Valid"] == True
                output = parcelsBackyard.loc[mask]
            # write to file
            output.to_file(path + yardOption + "/" + setback + FARLC + housingType + treeOption + yardOption + ".gpkg", driver="GPKG")

    # front and back yard


    # ADU type


    # ADU number


    # parking

# === STEP 3: WALK SCORE, BIKE SCORE, TRANSIT SCORE, DENSITY, MEDIAN HHI ===============================================
def Step3():
    print("STEP 3: Loading data")
    # Projected Coordinate System: NAD 1983 StatePlane Virginia North FIPS 4501 (US Feet)
    # Projection: Lambert Conformal Conic
    # WKID: 2283
    fullParcels = gpd.read_file("../Output/Full_Parcels.gpkg", driver="GPKG", layer="FullParcels")
    walkScore = []
    bikeScore = []
    transitScore = []
    density = []
    medianHHI = []

    # lists of file path extensions
    setbacks = ["S5", "S10", "S20", "S30"]
    FARLCs = ["F.3", "F.5", "F.7", "F.9", "L20", "L40", "L60", "L80"]
    housingTypes = ["Single", "SingleMulti"]
    treePreservation = ["noTreePreservation", "TreePreservation"]
    frontBackYard = ["backOnly", "frontAndBack"]
    ADUType = "ADUType"
    ADUNumber = "ADUNumber"
    parking = ["noParkingRequired", "parkingRequired"]

    # for each combination of variables
    print("STEP 3: Running spatial joins")
    for setback, FARLC, housingType, treeOption, yardOption, parkingType in itertools.product(
    setbacks, FARLCs, housingTypes, treePreservation, frontBackYard, parking):
        path = ("../Output/" + setback + "/" + FARLC + "/" + housingType + "/" + treeOption + "/" +
                yardOption + "/" + ADUType + "/" + ADUNumber + "/" + parkingType + ".gpkg")
        parcels = gpd.read_file(path)

        # run spatial joins for each variable
        parcelsCenter = gpd.GeoDataFrame(geometry=parcels.geometry.centroid, crs="EPSG:2283")
        walkScoreCol = gpd.sjoin(parcelsCenter, walkScore, how="left", predicate="within")
        bikeScoreCol = gpd.sjoin(parcelsCenter, bikeScore, how="left", predicate="within")
        transitScoreCol = gpd.sjoin(parcelsCenter, transitScore, how="left", predicate="within")
        densityCol = gpd.sjoin(parcelsCenter, density, how="left", predicate="within")
        medianHHICol = gpd.sjoin(parcelsCenter, medianHHI, how="left", predicate="within")

        # drop duplicates from boundary points (if point is on a line)
        walkScoreCol = walkScoreCol[~walkScoreCol.index.duplicated(keep="first")]
        bikeScoreCol = bikeScoreCol[~bikeScoreCol.index.duplicated(keep="first")]
        transitScoreCol = transitScoreCol[~transitScoreCol.index.duplicated(keep="first")]
        densityCol = densityCol[~densityCol.index.duplicated(keep="first")]
        medianHHICol = medianHHICol[~medianHHICol.index.duplicated(keep="first")]

        # create columns
        parcels[["Walk_Score", "Bike_Score", "Transit_Score", "Density", "MedianHHI"]] = pd.concat(
            [walkScoreCol["Walk_Score"], bikeScoreCol["Bike_Score"], transitScoreCol["Transit_Score"],
             densityCol["Density"], medianHHICol["MedianHHI"]], axis=1)

        # save file
        parcels.to_file(path, driver="GPKG")

def ADUCheckTest():
    box = gpd.read_file("../box2.gpkg")
    parcels = gpd.read_file("../Output/Test1.gpkg")
    parcels = parcels.overlay(box, how="intersection")
    # === TEST 3 ===
    # results = parcels.geometry.apply(ADUCheckBasic).apply(pd.Series)
    # parcels["Test"] = results[0]
    # parcels = parcels.drop(columns=[col for col in parcels.columns if parcels[col].dtype == "geometry"])
    # parcels = gpd.GeoDataFrame(parcels, geometry=results[1], crs="EPSG:2283")
    # parcels["Test"], parcels.geometry = parcels.geometry.apply(ADUCheckBasic)
    # parcels.to_file("../Output/Test3.gpkg", driver="GPKG", layer="FilteredFootprints")

    # === TEST 4 ===
    results = parcels.geometry.apply(SplitFrontBackYard).apply(pd.Series)
    frontYards = gpd.GeoDataFrame(geometry=results["Front_Yard"], crs="EPSG:2283")
    backYards = gpd.GeoDataFrame(geometry=results["Back_Yard"], crs="EPSG:2283")
    parcels = pd.concat([frontYards, backYards], ignore_index=True)
    parcels.to_file("../Output/Test4.gpkg", driver="GPKG", layer="FrontBackSplit")