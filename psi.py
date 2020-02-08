# -*- coding: UTF-8 -*-

#This is a version of puzzlescript video codec that doesn't use image compression.
#In other words, it can do 1/1 recreations of images.

import cv2
import sys
import os
import copy

#print debug info in the output file
debug = True

#the resolution of the image in tiles. Each tile is 5x5 pixels, so to get the resolution in pixels, multiply by 5.
tileW = 28
tileH = 21

#28 by 21 is ideal for dream seq.

#thresholds for various merges (I'll explain this someday... maybe)
#the higher the thresholds, the more the image will be compressed.
singleton_merge_threshold = 500
single_merge_threshold = 10000
double_merge_threshold = 15000
use_good_averaging = True

skip_alias = 20

#utility function
def saneIndex(listy,element):
	if(len(listy) == 0):
		return(-1)
	return(listy.index(element) if element in listy else -1)

path = os.path.dirname(os.path.abspath(__file__))

#this array should contain the filenames/pathnames of the images that will get output as a video.
#this is the script I used to load up the frames for Steamed Hams. Your video will probably look different, so you should change this.
files = ["images/screenshot (1).png","images/screenshot (2).png","images/screenshot (3).png","images/screenshot (4).png"]


pictures = []

#takes the pathnames from the files array and loads the pictures.
def loadPictures():
	for i in range(len(files)):
		pix = cv2.imread(path + "/" + files[i])
		pictures.append(cv2.resize(pix,(tileW*5,tileH*5),interpolation = cv2.INTER_AREA))

loadPictures()

#how far away are two colors? Low values mean the two colors are pretty similar, high values mean they're not.
#returns the sum of the squared distance of each channel.
def colorDistance(color1,color2):
	cr,cg,cb = color1
	cr = int(cr)
	cg = int(cg)
	cb = int(cb)
	
	pr, pg, pb = color2
	pr = int(pr)
	pg = int(pg)
	pb = int(pb)
	
	dist = (cr-pr,cg-pg,cb-pb)
	dist = dist[0]*dist[0] + dist[1]*dist[1] + dist[2]*dist[2]
	
	return(dist)

#takes two colors (and their frequencies) and averages them.
def averageColor(color1,color2,freq1,freq2):
	
	#if the use_good_averaging flag is true, we take frequency into account when averaging colors (the more frequent color is weighted more heavily)
	if(not use_good_averaging):
		freq1 = 1
		freq2 = 1
	
	cr,cg,cb = color1
	cr = int(cr)*freq1
	cg = int(cg)*freq1
	cb = int(cb)*freq1
	
	pr, pg, pb = color2
	pr = int(pr)*freq2
	pg = int(pg)*freq2
	pb = int(pb)*freq2
	
	total = freq1+freq2
	
	avg = (cr+pr,cg+pg,cb+pb)
	avg = (int(avg[0]/total),int(avg[1]/total),int(avg[2]/total))
	
	return(avg)

#reads an image and returns an array of pixels from a section.
def getTileArray(tx,ty,image):
	tileArr = []
	for i in range(5):
		for j in range(5):
			#the resized sometimes image discards the alpha channel, for whatever reason.
			#b, g, r, a = resizedPix[tx*5+j,ty*5+i]
			b, g, r = pictures[image][tx*5+i,ty*5+j]
			
			tileArr.append((r,g,b))
	
	return(tileArr)

def getColorPalette(arr):
	global aggressiveColorMerges
	global singleton_bit_mask
	
	#each element is a list of: [color,frequency]
	colorArr = []
	
	for i in arr:
		index = saneIndex(colorArr,i)
		
		if(index == -1):
			colorArr.append([i,1])
		else:
			colorArr[index][1] += 1
	
	#prune list to only 10 colors, because a puzzlescript tile can only have 10.
	while(len(colorArr) > 10):
		
		dist = 999999999
		closestA = -1
		closestB = -1
		
		for b in range(len(colorArr)):
			for a in range(b):
				thisDist = colorDistance(colorArr[a][0],colorArr[b][0])
				if(dist > thisDist):
					dist = thisDist
					closestA = a
					closestB = b
		
		
		colorA = colorArr[closestA]
		colorB = colorArr[closestB]
		colorArr.pop(closestB)
		colorArr.pop(closestA)
		colorArr.append([averageColor(colorA[0],colorB[0],colorA[1],colorB[1]),colorA[1]+colorB[1]])
	
	#we don't need frequency anymore
	for i in range(len(colorArr)):
		colorArr[i] = colorArr[i][0]
	
	#todo: sort color list for merging pourpouses
	return(colorArr)

def getClosestColor(color,palette):
	closest = -1
	dist = 999999999
	
	for i in range(len(palette)):
		
		thisDist = colorDistance(color,palette[i])
		
		if(dist > thisDist):
			dist = thisDist
			closest = i
	
	return(closest)

def splitIntoTiles(arr):
    global singleton_threshold
    
    #check if we should use a singleton
    
    sum_r = 0
    sum_g = 0
    sum_b = 0
    
    for i in arr:
        sum_r += i[0]
        sum_g += i[1]
        sum_b += i[2]
    
    sum_r /= 25
    sum_g /= 25
    sum_b /= 25
    
    sum_r = int(sum_r)
    sum_g = int(sum_g)
    sum_b = int(sum_b)
    
    sum_dist = 0
    cur_tile = 0
    
    while(cur_tile < 25):
        sum_dist += colorDistance((sum_r,sum_g,sum_b),arr[cur_tile])
        cur_tile += 1
    
    if(sum_dist < singleton_merge_threshold):
        return([(tuple([0] * 25),tuple([(sum_r,sum_g,sum_b)]))])
    
    #the tile data
    tileData = []
    #the palette
    colorArr = []
    
    tileStack = []
    
    shouldSplit = sum_dist > single_merge_threshold
    
    count = 0
    for i in arr:
        if(count > 21):
            shouldSplit = False
        count += 1
        
        index = saneIndex(colorArr,i)
        
        if(index == -1):
            if(len(colorArr) == 10 and shouldSplit):
                used = len(tileData)
                while(len(tileData) < 25):
                    tileData.append(-1)
                tileStack.append((tuple(tileData),tuple(colorArr)))
                tileData = []
                for j in range(used):
                    tileData.append(-1)
                colorArr = [i]
                tileData.append(0)
                shouldSplit = (sum_dist > double_merge_threshold)
                #print(shouldSplit)
                continue
            colorArr.append(i)
            index = len(colorArr)-1
         
        tileData.append(index)
    
    if(len(colorArr) > 10):
        pal_input = []
        for i in tileData:
            if(i == -1):
                continue
            pal_input.append(colorArr[i])
        palette = getColorPalette(pal_input)
        for i in range(len(tileData)):
            if(tileData[i] == -1):
                continue
            tileData[i] = getClosestColor(colorArr[tileData[i]],palette)
        tileStack.append((tuple(tileData),tuple(palette)))
    else:
        tileStack.append((tuple(tileData),tuple(colorArr)))
    
    
    return(tileStack)

def htmlColor(r,g,b):
	
	sr = hex(r)
	sg = hex(g)
	sb = hex(b)
	
	sr = sr[2:]
	sg = sg[2:]
	sb = sb[2:]
	
	sr = ("0" + sr if len(sr) == 1 else sr)
	sg = ("0" + sg if len(sg) == 1 else sg)
	sb = ("0" + sb if len(sb) == 1 else sb)
	
	return("#" + sr + sg + sb)

#this function will format our tiles in a way that puzzlescript understands.
def printTile(tile,palette,name):
	stringy = name
	stringy += "\n"
	for i in palette:
		r, g, b = i
		curPixel = htmlColor(r,g,b)
		stringy += curPixel + " "
	stringy += "\n"
	if(len(palette) > 1 or tile[0] == -1 or tile[24] == -1):
		for i in range(len(tile)):
			if(tile[i] == -1):
				stringy += "."
			else:
				stringy += str(tile[i])
			if(i % 5 == 4):
				stringy += "\n"
	#print(tile)
	#print(stringy)
	stringy += "\n"
	
	return(stringy)



globalTiles = []

tileLayouts = []
collisionLayer = []

tileHash = {}

singletons = 0
singles = 0
doubles = 0
triples = 0

temporalMerges = 0
neighborMerges = 0

#this is where the bulk of the work happens.
#It takes the pictures and turns them into grids of tiles.
def genImage():
    global singletons
    global singles
    global doubles
    global triples
    
    tileNum = -1
    
    for pix in range(len(pictures)):
        
        tileLayouts.append([])
        current = len(tileLayouts)-1
        
        for i in range(tileH):
            for j in range(tileW):
                
                nextLoc = len(tileLayouts[current])
                
                tilePixels = getTileArray(i,j,pix)
                tiles = splitIntoTiles(tilePixels)
                
                if(len(tiles) == 2):
                    collisionLayer.append(0)
                    collisionLayer.append(1)
                elif(len(tiles) != 1):
                    collisionLayer.append(0)
                    collisionLayer.append(1)
                    collisionLayer.append(2)
                
                for tile in range(len(tiles)):
                    
                    #tile = (tuple(adjTile),tuple(palette))
                    
                    #print(tiles[tile] not in tileHash)
                    
                    if((len(tiles) > 1 or tiles[tile] not in tileHash)):
                        
                        #add and use new tile
                        globalTiles.append(tiles[tile])
                        if(tile == 0):
                            tileNum += 1
                            tileLayouts[current].append(tileNum)
                        if(len(tiles) == 1):
                            tileHash[tiles[tile]] = tileNum
                            collisionLayer.append(0)
                            #tileLayouts[current].append(len(globalTiles-)
                        
                        if(len(tiles[tile][1]) == 1):
                            singletons += 1
                        elif(len(tiles) == 1):
                            singles += 1
                        elif(len(tiles) == 2):
                            doubles += 1
                        elif(len(tiles) == 3):
                            triples += 1
                        
                    else:
                        #print(str(len(globalTiles)) + " => " + str(tileHash[tiles[tile]]))
                        #we already generated an identical tile, so use that
                        tileLayouts[current].append(tileHash[tiles[tile]])

genImage()

#this is where we output our work to a file.

file = ""

if(debug):
	file += "(\ntiles used: " + str(len(globalTiles)) + "/" + str(tileW*tileH) + "\nsingletons: " + str(singletons) + "\nsingles: " + str(singles) + "\ndoubles: " + str(doubles) + "\ntriples: " + str(triples) + "\n)\n\n"
	print(str(len(globalTiles)) + " tiles")

file += "title puzzlescript images\nauthor ethan clark\n\n========\nOBJECTS\n========\n\nbackground\nblack\n\n"

for i in range(len(globalTiles)):
		
		tile = globalTiles[i]
		
		file += printTile(tile[0],tile[1],"t" + str(i))

file += "=======\nLEGEND\n=======\n\nplayer = t0\n"


#js script used to generate alias:
#
#str = ""
#for(var i = 1024; i < 2048; i++){
#
#if(String.fromCharCode(i).toUpperCase().charCodeAt(0) != i){continue;}
#
#str += String.fromCharCode(i);
#
#}

#so, puzzlescript basically requires us to have a one character name for each tile we use in a level
#and we use every tile we generate in a level.
#thankfully, through the magic of unicode, we can make lots of one character names!
#puzzlescript didn't like some of the characters I tried to use, so I had to remove them from the alias.

alias = open("./alias.txt", encoding='utf-8').read();

#24576


#the rest is just printing out the file some more.

#for i in range(len(globalTiles)):

currentTile = 0
currentAlias = 0
img = 0

#print(collisionLayer)
#print(tileLayouts)

while(currentTile < len(globalTiles)):
    file += alias[currentAlias+skip_alias] + " = t" + str(currentTile)
    
    currentTile += 1
    while(currentTile < len(globalTiles) and collisionLayer[currentTile] > 0):
        file += " and t" + str(currentTile)
        currentTile += 1
    file += "\n"
    currentAlias += 1


file += "\n=======\nSOUNDS\n=======\n\n================\nCOLLISIONLAYERS\n================\n\nbackground\n"

for layer in range(3):
    for i in range(len(globalTiles)):
        if(collisionLayer[i] == layer):
            #print(str(layer) + str(i))
            file += "t" + str(i) + ","
    file += "\n"

file += "\n"

file += "======\nRULES\n======\n\n[] -> win\n\n"


file += "==============\nWINCONDITIONS\n==============\n\n=======\nLEVELS\n=======\n\n"

for i in range(len(tileLayouts)):
	for j in range(tileW*tileH):
		file += alias[tileLayouts[i][j]+skip_alias]
		if(j % tileW == tileW-1):
			file += "\n"
	file += "\n"

#puts the contents of the file into standard out. If you're on Linux, you can pipe the output to a text file.
#or, you might want to save the output to a file by some other, less Linux-y means.
#print(file)
fileOut = open("./output.txt",'w', encoding="utf-8")
fileOut.write(file)