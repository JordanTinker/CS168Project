#This file is for functions dealing with extracting information from .nii files
#Uses NiBabel http://nipy.org/nibabel/gettingstarted.html

import os
import numpy as np
import nibabel as nib
from PIL import Image
import time


class BrainImage:
	#This class represents a 3D brain image given in an NII file, and defines functions to operate on them
	def __init__(self, filename):
		self.filename = filename
		self.img = nib.load(filename)
		self.data = self.img.get_data()

	def printInfo(self):
		print("Printing information for {0}".format(self.filename))
		obj = self.img.dataobj
		isArray = nib.is_proxy(obj)
		print("Proxy: {0}".format(str(isArray)))
		data = self.img.get_data()
		print("Shape:\n{0}".format(str(data.shape)))
		print("Array:\n{0}".format(data[:, :, 115]))

	def getPNGFromSlice(self, numSlice, outfile):
		s = self.data[:, :, numSlice].T
		for x in np.nditer(s, op_flags=['readwrite']):
			x[...] = np.uint8(np.float64(x/1000)*255)
		im = Image.fromarray(s.astype(np.uint8), mode='L')
		im.save(outfile)

	#return a Numpy array containing a 33x33 patch centered around the x,y coordinate in the z plane
	def getPatch(self, x, y, z):
		return self.data[(x-16):(x+17), (y-16):(y+17), z]

	#save a patch as a PNG
	def getPNGFromPatch(self, x, y, z, outfile):
		patch = self.getPatch(x, y, z)
		for x in np.nditer(patch, op_flags=['readwrite']):
			x[...] = np.uint8(np.float64(x/1000)*255)
		im = Image.fromarray(patch.astype(np.uint8), mode='L')
		im.save(outfile)

	def getValueAt(self, x, y, z):
		return self.data[x, y, z]


class PatientData:

	def __init__(self, name):
		self.name = name
		path = "data/" + name + "/" + name
		#print(path)
		self.flair_data = BrainImage(path + '_flair.nii.gz')
		self.t1_data = BrainImage(path + '_t1.nii.gz')
		self.t1ce_data = BrainImage(path + '_t1ce.nii.gz')
		self.t2_data = BrainImage(path + '_t2.nii.gz')
		self.groundtruth = BrainImage(path + '_seg.nii.gz')

	def getGroundTruth(self, x, y, z):
		return self.groundtruth.getValueAt(x, y, z)

	#old method of generating patches for input. Resulted in imbalenced classes
	def oldGetNPatches(self, n):
		numlist = []
		for i in range(n):
			numlist.append((np.random.randint(16, high=224), np.random.randint(16, high=224), np.random.randint(0, high=155)))
		#print("Numlist length is {0}".format(len(numlist)))
		patchlist = []
		for i in range(n):
			coords = numlist[i]
			flair_patch = self.flair_data.getPatch(coords[0], coords[1], coords[2])
			t1_patch = self.t1_data.getPatch(coords[0], coords[1], coords[2])
			t1ce_patch = self.t1ce_data.getPatch(coords[0], coords[1], coords[2])
			t2_patch = self.t2_data.getPatch(coords[0], coords[1], coords[2])
			stacked = np.stack((flair_patch, t1_patch, t1ce_patch, t2_patch))
			patchlist.append(stacked)
		#print("Patchlist length is {0} before validation".format(len(patchlist)))
		valid_patches = []
		labels = []
		for i in range(n):
			if validatePatch(patchlist[i][0]):
				valid_patches.append(patchlist[i])
				coords = numlist[i]
				labels.append(self.groundtruth.getValueAt(coords[0], coords[1], coords[2]))
		#print("There are {0} valid patches".format(len(valid_patches)))
		#print("There are {0} labels".format(len(labels)))

		result_patches = np.array([]).reshape(0, 4, 33, 33)
		result_labels = np.array([]).reshape(0, 1)
		for e in valid_patches:
			e2 = e.reshape(1, 4, 33, 33)
			result_patches = np.vstack((result_patches, e2))
		for e in labels:
			e2 = np.array([e]).reshape(1, 1)
			result_labels = np.vstack((result_labels, e2))

		#print("Shape of result_patches: {0} Shape of labels: {1}".format(result_patches.shape, result_labels.shape))

		return (result_patches, result_labels)

	#Generate patches for input. Generates roughly equal amounts for each class of data
	def getNPatches(self, num):
		#find indices of occurances of each class
		class0 = np.argwhere(self.groundtruth.data == 0)
		class1 = np.argwhere(self.groundtruth.data == 1)
		class2 = np.argwhere(self.groundtruth.data == 2)
		class4 = np.argwhere(self.groundtruth.data == 4)

		#randomly select indices within each class
		#i0 = np.random.randint(class0.shape[0], size=n/4)
		n_each = int(num/4)
		i1 = np.random.randint(class1.shape[0], size=n_each)
		i2 = np.random.randint(class2.shape[0], size=n_each)
		i4 = np.random.randint(class4.shape[0], size=n_each)

		patchlist = []
		labels = []
		while (len(patchlist) < n_each):
			n = class0[np.random.randint(class0.shape[0])]
			x = n[0]
			y = n[1]
			z = n[2]
			if (x < 16 or x >= 224 or y < 16 or y >= 224):
				continue
			else:
				flair_patch = self.flair_data.getPatch(x, y, z)
				t1_patch = self.t1_data.getPatch(x, y, z)
				t1ce_patch = self.t1ce_data.getPatch(x, y, z)
				t2_patch = self.t2_data.getPatch(x, y, z)
				if(validatePatch(flair_patch)):
					stacked = np.stack((flair_patch, t1_patch, t1ce_patch, t2_patch))
					patchlist.append(stacked)
					labels.append(0)

		flair_patch = self.flair_data.getPatch(18, 18, z)
		t1_patch = self.t1_data.getPatch(18, 18, z)
		t1ce_patch = self.t1ce_data.getPatch(18, 18, z)
		t2_patch = self.t2_data.getPatch(18, 18, z)
		stacked = np.stack((flair_patch, t1_patch, t1ce_patch, t2_patch))
		patchlist.append(stacked)
		labels.append(0)

		for i in i1:
			n = class1[i]
			x = n[0]
			y = n[1]
			z = n[2]
			flair_patch = self.flair_data.getPatch(x, y, z)
			t1_patch = self.t1_data.getPatch(x, y, z)
			t1ce_patch = self.t1ce_data.getPatch(x, y, z)
			t2_patch = self.t2_data.getPatch(x, y, z)
			stacked = np.stack((flair_patch, t1_patch, t1ce_patch, t2_patch))
			patchlist.append(stacked)
			labels.append(1)

		for i in i2:
			n = class2[i]
			x = n[0]
			y = n[1]
			z = n[2]
			flair_patch = self.flair_data.getPatch(x, y, z)
			t1_patch = self.t1_data.getPatch(x, y, z)
			t1ce_patch = self.t1ce_data.getPatch(x, y, z)
			t2_patch = self.t2_data.getPatch(x, y, z)
			stacked = np.stack((flair_patch, t1_patch, t1ce_patch, t2_patch))
			patchlist.append(stacked)
			labels.append(2)

		for i in i4:
			n = class4[i]
			x = n[0]
			y = n[1]
			z = n[2]
			flair_patch = self.flair_data.getPatch(x, y, z)
			t1_patch = self.t1_data.getPatch(x, y, z)
			t1ce_patch = self.t1ce_data.getPatch(x, y, z)
			t2_patch = self.t2_data.getPatch(x, y, z)
			stacked = np.stack((flair_patch, t1_patch, t1ce_patch, t2_patch))
			patchlist.append(stacked)
			labels.append(3)

		result_patches = np.array([], dtype='int').reshape(0, 4, 33, 33)
		result_labels = np.array([], dtype='int').reshape(0, 1)
		for e in patchlist:
			e2 = e.reshape(1, 4, 33, 33)
			result_patches = np.vstack((result_patches, e2))
		for e in labels:
			e2 = np.array([e]).reshape(1, 1)
			result_labels = np.vstack((result_labels, e2))

		return (result_patches, result_labels)

	#Get a line of data from the 2D brain image for prediction
	def getPredictDataLine(self, numSlice, numLine):
		patchlist = []
		patches_start = time.time()
		for col in range(16, 224):
			coords = (numLine, col, numSlice)
			flair_patch = self.flair_data.getPatch(coords[0], coords[1], coords[2])
			t1_patch = self.t1_data.getPatch(coords[0], coords[1], coords[2])
			t1ce_patch = self.t1ce_data.getPatch(coords[0], coords[1], coords[2])
			t2_patch = self.t2_data.getPatch(coords[0], coords[1], coords[2])
			stacked = np.stack((flair_patch, t1_patch, t1ce_patch, t2_patch))
			patchlist.append(stacked)
		patches_time = time.time() - patches_start
		#print("Made patches in {0}s".format(patches_time))
		reshape_start = time.time()
		result_patches = np.array([], dtype='int').reshape(0, 4, 33, 33)
		for e in patchlist:
			e2 = e.reshape(1, 4, 33, 33)
			result_patches = np.vstack((result_patches, e2))
		reshape_time = time.time() - reshape_start
		#print("Reshaped in {0}s".format(reshape_time))
		return result_patches


def validatePatch(patch):
	# A patch is valid if less than 60% of the pixels in the image are value 0 (black background)
	totalZeros = 0
	for x in np.nditer(patch):
		if x == 0:
			totalZeros += 1
	if (totalZeros > 653):
		return False
	else:
		return True

#takes the data component of a BrainImage and a 240x240x155 segmentation ndarray and returns a 240x240 ndarray of the original data overwritten by segmentation highlighting
def getHighlightedPNG(base_image, segmentation, numSlice):
	base_slice = base_image[:, :, numSlice].T
	for x in np.nditer(base_slice, op_flags=['readwrite']):
		x[...] = np.uint8(np.float64(x/1000)*255)
	im = Image.fromarray(base_slice.astype(np.uint8), mode='L')
	im = im.convert(mode="RGB")
	for x in range(240):
		for y in range(240):
			current_value = segmentation[x][y]
			new_pixel = (0, 0, 0)
			if current_value == 0:
				pass
			elif current_value == 1:	#Non-enhancing tumor core
				new_pixel = (237, 26, 18) #Red
				im.putpixel((x,y), new_pixel)
			elif current_value == 2:	#peritumoral edema
				new_pixel = (18, 237, 33) #green
				im.putpixel((x,y), new_pixel)
			elif current_value == 3:
				new_pixel = (18, 55, 237) #blue
				im.putpixel((x,y), new_pixel)
			elif current_value == 4:	#GD-enhancing tumor
				new_pixel = (18, 55, 237) #blue
				im.putpixel((x,y), new_pixel)
	return im

def getPNGFromAnyPatch(patch, outfile):
		for x in np.nditer(patch, op_flags=['readwrite']):
			x[...] = np.uint8(np.float64(x/1000)*255)
		im = Image.fromarray(patch.astype(np.uint8), mode='L')
		im.save(outfile)



#Generate professional segmentation images for each slice in a sample image
if __name__ == '__main__':
	name = "Brats18_TCIA02_607_1"
	p = PatientData(name)
	for z in range(155):
		im = getHighlightedPNG(p.flair_data.data, p.groundtruth.data[:, :, z], z)
		im.save("groundtruth/segmentation_{0}_{1}.png".format(name, z))
	
	