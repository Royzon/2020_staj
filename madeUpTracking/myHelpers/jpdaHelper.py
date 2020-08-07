from scipy.stats import norm, multivariate_normal
import numpy as np
import scipy.linalg as linalg
from numpy.linalg import inv

import math


"""
    References:

    [BYL95] : MultiTarget-Multisensor Tracking Yaakov Bar-Shalom 1995
    [AR07] : Masters Thesis: 3D-LIDAR Multi Object Tracking for Autonomous Driving

"""

"""
    for stateMean, stateCovariance in zip(modeStateMeans, modeStateCovariance):

        distancesToMeasurements = [] 

        stateCovarianceInverse = np.linalg.pinv(stateCovariance)

        for measurement in allMeasurements:

            distance = np.dot((measurement - stateMean).T, np.dot(stateCovarianceInverse, (measurement - stateMean)) )
            distancesToMeasurements.append(distance)
        
        modeDistancesToMeasurements.append(distancesToMeasurements)

    validatedMeasurements = np.sum(np.array(modeDistancesToMeasurements, dtype="float") < gateThreshold, axis=0) == modeStateMeans.shape[0]
    validatedMeasurements = allMeasurements[validatedMeasurements]
"""


def generateAssociationEvents(validationMatrix): #checkCount : 1
    
    """
        Description:
            ---
        Input:
            validationMatrix: np.array(shape = (m_k, Nr+1))
        Output:
            associationEvents : np.array(shape = (numberOfEvents(not known in advance), m_k, 1))
    """
    
    associationEvents = []

    m_k = validationMatrix.shape[0]
    exhaustedMeasurements = np.zeros((m_k), dtype=int)

    usedTrackers = None
    previousEvent = np.zeros(shape = (m_k), dtype = int) - 1
    burnCurrentEvent = None

    while(not exhaustedMeasurements[0]):

        event = np.zeros(shape = (m_k), dtype=int)
        burnCurrentEvent = False
        usedTrackers = []

        for i,validationVector in enumerate(validationMatrix):
            
            #Note: validationVector corresponds to a measurement -> measurement_validationVector : [val?_t0, val?_t1, ..., val?_tNr]

            if(previousEvent[i] == -1):
                event[i] = 0 #first t_0 will be considered, note it always a choice since measurement can be not related with any track
            else:

                nextMeasurementIndex = i+1
                if(nextMeasurementIndex == m_k or exhaustedMeasurements[nextMeasurementIndex]):

                    if(nextMeasurementIndex != m_k):
                        exhaustedMeasurements[nextMeasurementIndex:] = 0
                        previousEvent[nextMeasurementIndex:] = -1

                    
                    nextTrackIndex = previousEvent[i]
                    
                    
                    while(validationVector.shape[0]-1 > nextTrackIndex):
                        if(nextTrackIndex != previousEvent[i]):
                            if((nextTrackIndex not in usedTrackers) and (validationVector[nextTrackIndex])):
                                break
                        nextTrackIndex +=1
                        
                    if(not validationVector[nextTrackIndex] or nextTrackIndex == previousEvent[i] or nextTrackIndex in usedTrackers):
                        burnCurrentEvent = True
                        exhaustedMeasurements[i] = 1
                        break
                    

                    usedTrackers.append(nextTrackIndex)
                    event[i] = nextTrackIndex
                
                else:   
                    event[i] = previousEvent[i]
                    usedTrackers.append(previousEvent[i])
            
        if(burnCurrentEvent):
            
            continue

        previousEvent = np.copy(event)
        associationEvents.append(event)
    
    return np.array(associationEvents, dtype=int)

def createValidationMatrix(measurements, tracks, gateThreshold): #checkCount : 1

    """
        Description: 
            This function creates a validation matrix and the indexes of the measurements that are in range

            Inputs:
                measurements : np.array(shape =(m_k, dimZ))
                tracks : list of len = Nr of track objects
                gateThreshold : float(0,1)

            Returns:

                validateMeasurementsIndexes: np.array(shape = (numOfSuceesfulGatedMeasurements(not known in advance),1))
                    
                     "The indexes of the measurements which are used to create the validationMatrix. The indexes indicating the
                     element index of that measurement inside the input 'measurements', the order measurements hold should not change"

                    [page 311, Remark, BYL95]

                validationMatrix: np.array(shape = (m_k, Nr+1))

                    The matrix whose shape is ( len(validatedMeasurements), (len(targets) + 1) )
                    The binary elements it contains represents if that column(target) and row(measurement) are in the gating range

                    [page 312, 6.2.2-2, BYL95]
    """

    validationMatrix = []
    validatedMeasurementIndexes = []

    for i,measurement in enumerate(measurements):

        validationVector = [1] # inserting a 1 because -> [page 312, 6.2.2-1, BYL95]
        measurement = np.expand_dims(measurement, axis=1)

        for track in tracks:

            mahalanobisDistanceSquared_ = mahalanobisDistanceSquared(measurement, track.z_prior, track.S_prior)

            if(mahalanobisDistanceSquared_ < gateThreshold):
                validationVector.append(1)
            else:
                validationVector.append(0)

        validationVector = np.array(validationVector)

        if(np.sum(validationVector) > 1): # this means that measurement is validated at least for one track -> worth to consider hence append
            
            validationMatrix.append(validationVector)
            validatedMeasurementIndexes.append(i)

    validationMatrix = np.array(validationMatrix, dtype=int)
    validatedMeasurementIndexes = np.expand_dims(np.array(validatedMeasurementIndexes), axis=1)

    return (validatedMeasurementIndexes, validationMatrix)



def mahalanobisDistanceSquared(x, mean, cov): #checkCount : 1, 1/2*confident

    """
    Computes the Mahalanobis distance between the state vector x from the
    Gaussian `mean` with covariance `cov`. This can be thought as the number
    of standard deviations x is from the mean, i.e. a return value of 3 means
    x is 3 std from mean.

    """
    if x.shape != mean.shape:
        raise ValueError("length of input vectors must be the same")

    y = x - mean
    S = np.atleast_2d(cov)

    dist = float(np.dot(np.dot(y.T, inv(S)), y))
    return dist
    

def calculateTheProbabilityOfTheMeasurement(measurement, z, S):

    """

        Description:
            Calculate the probability that 'measurement' is measured w.r.t z and S
        
        [page 314, (6.2.3-4) BYL95]
        
        Input:
            measurement : np.array(shape=(dimZ, 1))
            z : np.array(shape = (dimZ, 1))
            S : np.array(shape = (dimZ, dimZ))
        Output:
            probability : float(0,1)

    """

    return multivariate_normal.pdf(measurement.flatten(), z.flatten(), S, True) 



def calculateJointAssociationProbability_parametric(jAE, measurements, tracks, spatialDensity, PD):

    """
        Description:
            This function calculates the possibility of the association event(jAE) occurrence
            using the parametric JPDA

            Note that, the value returned from this function is not exact, the normalization constant is undetermined
            One needs to divide this returned value with the sum of all joint association probabilities to normalize

            [page 317, (6.2.4-4) BYL95]
        
        Input:
 
        jAE : np.array(shape : (m_k, 1))
            "The elements of the vector represents the targetIndexes the measurements are associated with" [page 312, (6.2.2-3) BYL95]  
           
        measurements : np.array(shape=(m_k,1))
           
        tracks: list of len = Nr of track objects

        spatialDensity : float
           "The poisson parameter that represents the number of false measurements in a unit volume" [page 317, (6.2.4-1) BYL95]

        PD: float
           "Detection probability"           
        
        Output:
            associationProbability : float
    """

    numberOfDetections = np.sum(jAE>0)

    measurementProbabilities = 1

    for measurementIndex, associatedTrack in enumerate(jAE):

        trackPriorMean = tracks[associatedTrack].z_prior
        trackPriorS = tracks[associatedTrack].S_prior

        measurementProbabilities *= calculateTheProbabilityOfTheMeasurement(measurements[measurementIndex], trackPriorMean, trackPriorS)
        measurementProbabilities /= spatialDensity

    return measurementProbabilities * pow(PD, numberOfDetections) * pow(1-PD, tracks.shape[0] - numberOfDetections)





def calculateJointAssociationProbability_nonParametric(jAE, measurements, tracks, volume, PD):

    """
        Description:
            This function calculates the possibility of the association event(jAE) occurrence
            using the non parametric JPDA

            Note that, the value returned from this function is not exact, the normalization constant is undetermined
            One needs to divide this returned value with the sum of all joint association probabilities to normalize

            [page 318, (6.2.4-8) BYL95]
        
        Input:
 
        jAE : np.array(shape : (m_k, 1))
            "The elements of the vector represents the targetIndexes the measurements are associated with" [page 312, (6.2.2-3) BYL95]  
           
        measurements : np.array(shape=(m_k,1))
           
        tracks: list of len = Nr of track objects

        volume : float
           "volume of the surveillance region" [page 314, (6.2.3-5) BYL95]

        PD: float
           "Detection probability"           
        
        Output:
            associationProbability : float
    """

    numberOfDetections = np.sum(jAE>0)
    m_k = jAE.shape[0]

    measurementProbabilities = 1
    
    def fact(n):
        a = 1
        for i in range(n):
            a *= (i+1)
        return a

    for measurementIndex, associatedTrack in enumerate(jAE):

        trackPriorMean = tracks[associatedTrack].z_priorMean
        trackS = tracks[associatedTrack].S

        measurementProbabilities *= calculateTheProbabilityOfTheMeasurement(measurements[measurementIndex], trackPriorMean, trackS)
        measurementProbabilities *= volume

    return measurementProbabilities * fact(m_k - numberOfDetections) * pow(PD, numberOfDetections) * pow(1-PD, tracks.shape[0] - numberOfDetections)




def calculateMarginalAssociationProbabilities(events, measurements, tracks, spatialDensity, PD):

    """
        Description:
            Calculates the marginal association probabilities, ie. Beta(j,t) for each measurement and tracks.
            Note that the value returned from the calculateJointAssociationProbability function is not normalized
            Hence one needs to normalize the calculated probabilities.

            calculation : [page 317, (6.2.5-1) BYL95]
            normalization : [page 39, (3-45) AR07]

        'measurements' : numpy array of shape (m,)

        'tracks' : numpy array of shape (Nt,)
    
        'spatialDensity': 

            The poisson parameter that represents the number of false measurements in a unit volume

            [page 317, (6.2.4-1) BYL95]

        "PD" :

            Detection probability            

    """
    
    numberOfMeasurements = measurements.shape[0]
    numberOfTracks = tracks.shape[0]

    marginalAssociationProbabilities = np.zeros((numberOfMeasurements, numberOfTracks))

    sumOfEventProbabilities = 0 #will be used to normalize the calculated probabilities

    for event in events:

        eventProbability = calculateJointAssociationProbability_parametric(event, measurements, tracks, spatialDensity, PD)
        sumOfEventProbabilities += eventProbability

        for measurementIndex, trackIndex in enumerate(event):

            marginalAssociationProbabilities[measurementIndex, trackIndex] += eventProbability

    marginalAssociationProbabilities /= sumOfEventProbabilities #normalize the probabilites

    return marginalAssociationProbabilities