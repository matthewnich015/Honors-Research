# SCOPE: runs the calculations to determine the amount of ADUs allowed for each combination of variables

import math
import random
import pandas as pd
import geopandas as gpd
import shapely as shapely

# === GLOBAL VARIABLES =================================================================================================
# full area data paths (38,683 parcels)
pF, bF = "../Data/Parcel_Polygons/REA_Property_Polygons.shp", "../Data/Building_Polygons/Building_Polygons.shp"
sF, zF = "../Data/Street_Network/Street_Network.shp", "../Data/Zoning_Polygons/Zoning_Polygons.shp"
fF, dF = "../Data/FEMA_Flood_Zone_Polygons/FEMA_Flood_Zone_Polygons.shp", "../Data/Driveway_Polygons/Driveway_Polygons.shp"
hF = "../Data/Zoning_Historic_District_Polygons/Zoning_Historic_District_Polygons.shp"
# large test data paths (4,159 parcels)
pL, bL = "../Data/Parcel_Polygons_Large/Parcel_Polygons_Large.shp", "../Data/Building_Polygons_Large/Building_Polygons_Large.shp"
sL, zL = "../Data/Street_Network_Large/Street_Network_Large.shp", "../Data/Zoning_Polygons_Large/Zoning_Polygons_Large.shp"
fL, dL = "../Data/FEMA_Flood_Zone_Polygons_Large/FEMA_Flood_Zone_Polygons_Large.shp", "../Data/Driveway_Polygons_Large/Driveway_Polygons_Large.shp"
hL = "../Data/Zoning_Historic_District_Polygons_Large/Zoning_Historic_District_Polygons_Large.shp"
# small test area data paths (339 parcels)
pS, bS = "../Data/Parcel_Polygons_Small/Parcel_Polygons_Small.shp", "../Data/Building_Polygons_Small/Building_Polygons_Small.shp"
sS, zS = "../Data/Street_Network_Small/Street_Network_Small.shp", "../Data/Zoning_Polygons_Small/Zoning_Polygons_Small.shp"
fS, dS = "../Data/FEMA_Flood_Zone_Polygons_Small/FEMA_Flood_Zone_Polygons_Small.shp", "../Data/Driveway_Polygons_Small/Driveway_Polygons_Small.shp"
hS = "../Data/Zoning_Historic_District_Polygons_Small/Zoning_Historic_District_Polygons_Small.shp"
# master data paths (default full area, change to test cases via functions)
(parcelsPath, buildingFootprintPath, streetNetworkPath, zoningPath, floodplainsPath,
 historicDistrictsPath, drivewaysPath) = pF, bF, sF, zF, fF, hF, dF

# === PRIVATE FUNCTIONS ================================================================================================
# set test cases
def SetDataPathsToLargeTest():
    global parcelsPath, buildingFootprintsPath, streetNetworkPath, zoningPath, floodplainsPath, historicDistrictsPath, drivewaysPath
    (parcelsPath, buildingFootprintsPath, streetNetworkPath, zoningPath, floodplainsPath,
     historicDistrictsPath, drivewaysPath) = pL, bL, sL, zL, fL, hL, dL

def SetDataPathsToSmallTest():
    global parcelsPath, buildingFootprintsPath, streetNetworkPath, zoningPath, floodplainsPath, historicDistrictsPath, drivewaysPath
    (parcelsPath, buildingFootprintsPath, streetNetworkPath, zoningPath, floodplainsPath,
     historicDistrictsPath, drivewaysPath) = pS, bS, sS, zS, fS, hS, dS


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
    root = "../Data/"
    buildingFootprints = gpd.read_file(root + "Building_Polygons/Building_Polygons.shp")

    # find the area of buildings in the parcel
    fullParcel["buildings"] = [gpd.clip(buildingFootprints, row.geometry).geometry.union_all() for idx, row in fullParcel.iterrows()]
    fullParcel["areaExisting"] = fullParcel["buildings"].area

    # calculate lot coverage
    fullParcel["totalArea"] = fullParcel["areaExisting"] + buildingArea
    fullParcel["lotCoverage"] = fullParcel["totalArea"] / fullParcel.geometry.area
    return fullParcel

def CalculateFAR(fullParcel: gpd.GeoDataFrame, buildingArea: float):
    root = "../Data/"
    buildingFootprints = gpd.read_file(root + "Building_Polygons/Building_Polygons.shp")

    # find the area of buildings in the parcel
    fullParcel["buildings"] = [gpd.clip(buildingFootprints, row.geometry).geometry.union_all() for idx, row in fullParcel.iterrows()]
    fullParcel["areaExisting"] = fullParcel["buildings"].area

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
                ADUT = shapely.translate(ADU, xoff=vars[1], yoff=vars[2])
                ADUT = shapely.rotate(ADUT, vars[3])
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
                            ADUT = shapely.translate(ADU, xoff=vars[1], yoff=vars[2])
                            ADUT = shapely.rotate(ADUT, vars[3])
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
    print("Splitting Yard")
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
        print("there are streets")
        for idx, row in bboxE.iterrows():
            edge = row.geometry
            edgeCenter = edge.centroid
            # check if the edge is close enough to mark as front yard
            distance = min(edgeCenter.distance(nearbyStreets.geometry))
            if distance < 50:
                print("found a front")
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
            print("using driveway")
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
            print(distIdx)
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
    print("STEP 0: Loading Data")
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

    # add all necessary columns into the geodataframe
    print("STEP 0: Adding columns to parcels to be filled in in steps 1, 2 and 3")
    parcelStart[["Total_Count", "Detatched_Count", "Attached_Count", "Existing_Count",
        "Walk_Score", "Bike_Score", "Transit_Score", "Near_Transit", "Median_Household_Income", "Median_Age"]] = None

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
    print("STEP 1: Loading Data")
    # Projected Coordinate System: NAD 1983 StatePlane Virginia North FIPS 4501 (US Feet)
    # Projection: Lambert Conformal Conic
    # WKID: 2283
    parcels = gpd.read_file("../Output/Step0_Parcels.gpkg", driver="GPKG", layer="ParcelStart")
    fullParcels = gpd.read_file("../Output/Step0_Full_Parcels.gpkg", driver="GPKG", layer="FullParcels")

    setbacks = [5, 10, 20, 30]
    FARs = [.3, .5, .7, .9]
    lotCoverages = [.2, .4, .6, .8]

    # Setbacks
    for setback in setbacks:
        parcelSetbacks = CalculateSetbacks(fullParcels, parcels, setback)
        result = parcelSetbacks.copy()
        result["Valid"] = parcelSetbacks.geometry.apply(ADUCheckBasic)
        result = result["Valid"] == True
        result.to_file("../Output/S" + str(setback) + "/S" + str(setback) + ".gpkg")

    # Lot Coverage
    for setback in setbacks:
        base = gpd.read_file("../Output/S" + str(setback) + "/S" + str(setback) + ".gpkg")
        result = CalculateLotCoverage(base, 17.65)
        for lotCoverage in lotCoverages:
            result["Valid"] = result["lotCoverage"] > lotCoverage
            result = result["Valid"] == True
            result = result.drop(columns=["lotCoverage", "totalArea", "areaExisting", "buildings"])
            result.to_file("../Output/S" + str(setback) + "/L" + str(lotCoverage * 100) +
                           "/S" + str(setback) + "L" + str(lotCoverage * 100) + ".gpkg")

    # FAR
    for setback in setbacks:
        base = gpd.read_file("../Output/S" + str(setback) + "/S" + str(setback) + ".gpkg")
        result = CalculateFAR(base, 17.65)
        for FAR in FARs:
            result["Valid"] = result["FAR"] > FAR
            result = result["Valid"] == True
            result = result.drop(columns=["FAR", "totalArea", "areaExisting", "buildings"])
            result.to_file("../Output/S" + str(setback) + "/F" + str(FAR).replace("0", "") +
                           "/S" + str(setback) + "F" + str(FAR).replace("0", "") + ".gpkg")




            


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