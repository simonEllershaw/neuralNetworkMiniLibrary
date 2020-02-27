from sklearn.calibration import CalibratedClassifierCV
import pickle
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn import preprocessing
from part2_claim_classifier import ClaimClassifier
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle
from sklearn.preprocessing import LabelBinarizer
from sklearn.metrics import roc_auc_score
import part2_claim_classifier as part2

def fit_and_calibrate_classifier(classifier, X, y):
    # DO NOT ALTER THIS FUNCTION
    X_train, X_cal, y_train, y_cal = train_test_split(
        X, y, train_size=0.85, random_state=0)
    classifier = classifier.fit(X_train, y_train)

    # This line does the calibration for you
    calibrated_classifier = CalibratedClassifierCV(
        classifier, method='sigmoid', cv='prefit').fit(X_cal, y_cal)
    return calibrated_classifier


# class for part 3
class PricingModel():
    # YOU ARE ALLOWED TO ADD MORE ARGUMENTS AS NECESSARY
    def __init__(self, calibrate_probabilities=False):
        """
        Feel free to alter this as you wish, adding instance variables as
        necessary.
        """
        self.y_mean = None
        self.calibrate = calibrate_probabilities
        # =============================================================
        # READ ONLY IF WANTING TO CALIBRATE
        # Place your base classifier here
        # NOTE: The base estimator must have:
        #    1. A .fit method that takes two arguments, X, y
        #    2. Either a .predict_proba method or a decision
        #       function method that returns classification scores
        #
        # Note that almost every classifier you can find has both.
        # If the one you wish to use does not then speak to one of the TAs
        #
        # If you wish to use the classifier in part 2, you will need
        # to implement a predict_proba for it before use
        # =============================================================
        self.base_classifier = ClaimClassifier()  # ADD YOUR BASE CLASSIFIER HERE

    # YOU ARE ALLOWED TO ADD MORE ARGUMENTS AS NECESSARY TO THE _preprocessor METHOD
    def _preprocessor(self, X_raw, training = False):
        """Data preprocessing function.

        This function prepares the features of the data for training,
        evaluation, and prediction.

        Parameters
        ----------
        X_raw : ndarray
            An array, this is the raw data as downloaded

        Returns
        -------
        X: ndarray
            A clean data set that is used for training and prediction.
        """
        # =============================================================
        # YOUR CODE HERE

        # Load simple data set used in part 2
        part2_headers = {"drv_age1", 'vh_age', 'vh_cyl', 'vh_din', 'pol_bonus', 'vh_sale_begin', 'vh_sale_end',
                         'vh_value', 'vh_speed','drv_age_lic1','pol_duration','pol_sit_duration','drv_age2'}
        # added from before
        # 'drv_age_lic1'
        #  pol_duration
        #  pol_sit_duration
        #  drv_age2

        required_attributes = X_raw[part2_headers]
        min_max_scaler = preprocessing.MinMaxScaler()

        # TODO Fix this needs to only calc scalers when passing the whole data set

        # Temporary hack
        x_normed = min_max_scaler.fit_transform(required_attributes)
        # End of Hack
        """
        # Use min/max normalisation
        if training:
            x_normed = min_max_scaler.fit_transform(required_attributes)
            self.normalisation = min_max_scaler.get_params()

        else:
            params = self.normalisation
            x_normed = min_max_scaler.fit_transform(required_attributes,y=None,params)
        """
        # Add extra columns here
        binarizer = LabelBinarizer()
        headers = {'drv_sex1', 'vh_type', 'pol_coverage', 'pol_usage'}

        for header in headers:
            data = X_raw[header]
            binarized = binarizer.fit_transform(data)
            if len(binarized[0]) > 1:
                binarized = binarized[:, :-1]

            binarized = np.asarray(binarized)

            total = np.append(x_normed, binarized, axis=1)

        return total

    def fit(self, X_raw, y_raw, claims_raw):
        """Classifier training function.

        Here you will use the fit function for your classifier.

        Parameters
        ----------
        X_raw : ndarray
            This is the raw data as downloaded
        y_raw : ndarray
            A one dimensional array, this is the binary target variable
        claims_raw: ndarray
            A one dimensional array which records the severity of claims

        Returns
        -------
        self: (optional)
            an instance of the fitted model

        """
        nnz = np.where(claims_raw != 0)[0]
        self.y_mean = np.mean(claims_raw[nnz])
        # =============================================================
        # REMEMBER TO A SIMILAR LINE TO THE FOLLOWING SOMEWHERE IN THE CODE
        X_clean = self._preprocessor(X_raw,training=True)

        #Split into training/Validation
        training_x, validation_x, training_y, validation_y = train_test_split(X_clean, y_raw, test_size=0.2)

        #Upsample data
        (unique, counts) = np.unique(training_y, return_counts=True)
        total_train = np.append(training_x, training_y, axis=1)
        total_train = pd.DataFrame(total_train)

        df_class_0 = total_train[total_train.iloc[:, -1] == 0]
        df_class_1 = total_train[total_train.iloc[:, -1] == 1]

        total_train_class_1_over = df_class_1.sample(counts[0], replace=True)
        test_over = pd.concat([df_class_0, total_train_class_1_over], axis=0)

        total_train = np.array(test_over)

        new_train_y = total_train[:, -1]
        new_train_x = total_train[:, :-1]
        new_train_y = np.expand_dims(new_train_y, 1)

        (unique, counts) = np.unique(new_train_y, return_counts=True)
        varaibles = len(new_train_x[0])

        validation_x = np.array(validation_x)
        validation_y = np.array(validation_y)

        # Find best parameters best classifier
        best_lr, best_epochs, multiplier, best_net = \
            part2.ClaimClassifierHyperParameterSearch(new_train_x, new_train_y, validation_x, validation_y, varaibles,
                                                      pricing=True)



        # THE FOLLOWING GETS CALLED IF YOU WISH TO CALIBRATE YOUR PROBABILITES
        if self.calibrate:
            self.base_classifier = fit_and_calibrate_classifier(
                self.base_classifier, X_clean, y_raw)
        else:
            self.base_classifier = best_net # Set classifier to model found
        return self.base_classifier

    def predict_claim_probability(self, X_raw, classifier =None):
        """Classifier probability prediction function.

        Here you will implement the predict function for your classifier.

        Parameters
        ----------
        X_raw : ndarray
            This is the raw data as downloaded

        Returns
        -------
        ndarray
            A one dimensional array of the same length as the input with
            values corresponding to the probability of beloning to the
            POSITIVE class (that had accidents)
        """
        # =============================================================
        # REMEMBER TO A SIMILAR LINE TO THE FOLLOWING SOMEWHERE IN THE CODE
        X_clean = self._preprocessor(X_raw)
        #X_clean = pd.DataFrame(X_clean)

        inputs = torch.Tensor(X_clean)
        output = self.base_classifier(inputs)
        prob_y = output.detach().numpy()

        return prob_y

    def predict_premium(self, X_raw):
        """Predicts premiums based on the pricing model.

        Here you will implement the predict function for your classifier.

        Parameters
        ----------
        X_raw : numpy.ndarray
            A numpy array, this is the raw data as downloaded

        Returns
        -------
        numpy.ndarray
            A one dimensional array of the same length as the input with
            values corresponding to the probability of belonging to the
            POSITIVE class (that had accidents)
        """
        # =============================================================
        # REMEMBER TO INCLUDE ANY PRICING STRATEGY HERE.
        # For example you could scale all your prices down by a factor
        premium_factor = 0.8

        premiums = self.predict_claim_probability(X_raw) * self.y_mean * premium_factor
        premiums = np.array(premiums)
        premiums = premiums.flatten()

        return premiums

    def save_model(self):
        """Saves the class instance as a pickle file."""
        # =============================================================
        with open('part3_pricing_model.pickle', 'wb') as target:
            pickle.dump(self, target)


def load_model():
    # Please alter this section so that it works in tandem with the save_model method of your class
    with open('part3_pricing_model.pickle', 'rb') as target:
        trained_model = pickle.load(target)
    return trained_model


def load_model2():
    # Please alter this section so that it works in tandem with the save_model method of your class
    with open('part2_claim_classifier.pickle', 'rb') as target:
        trained_model = pickle.load(target)
    return trained_model


if __name__ == "__main__":

    dat = pd.read_csv("part3_training_data.csv")
    attributes = dat.drop(columns=["claim_amount", "made_claim"])
    y = dat["made_claim"]
    claim_amounts = dat['claim_amount']

    # Clean data

    MyPricing_Model = PricingModel()

    # Join data
    #y = list(y)
    #labels = np.reshape(y, (len(y), 1))
    #total = np.append(x_clean, labels, axis=1)


    # Shuffle data and split
    X, Y = shuffle(attributes, y)

    train_x, test_x, train_y, test_y = train_test_split(X, Y, test_size=0.15)
    train_x = pd.DataFrame(train_x)
    train_y = pd.DataFrame(train_y)

    # Fit pricing model
    MyPricing_Model.fit(train_x, train_y, claim_amounts)
    probs = MyPricing_Model.predict_claim_probability(test_x)
    roc = roc_auc_score(test_y, probs)
    print("Roc Score on test Data: " + str(roc))
    prices = MyPricing_Model.predict_premium(attributes)
    print(prices)

    # Save Model
    print("Saving...")
    MyPricing_Model.save_model()

    # Load Model
    print("Loading...")
    loaded_model = PricingModel()
    loaded_model = load_model()

    # predict with loaded
    loaded_probs = loaded_model.predict_claim_probability(test_x)
    roc = roc_auc_score(test_y,loaded_probs)
    print("Roc Score on test Data: " + str(roc))



    """
    # New classifier Parameters
    
    multiplier = 4
    new_classifier = ClaimClassifier(variables=varaibles, multiplier=multiplier)
    new_classifier.train()
    learning = 0.002
    epochs = 124
    batch_size = len(new_train_x)
    criterion = nn.BCELoss()
    optimiser = torch.optim.Adam(new_classifier.parameters(), lr=learning)


    # Fit new classifier
    new_classifier.fit(new_train_x, new_train_y,criterion,optimiser,epochs,batch_size)

    best_lr, best_epochs, multiplier, best_net = \
        part2.ClaimClassifierHyperParameterSearch(new_train_x, new_train_y, valid_x, valid_y, varaibles, pricing=True)

    
    # Evaluate new classifier
    new_classifier.eval()
    new_classifier.evaluate_architecture(test_x, test_y)
    
    
    # Evaluate best net
    print("")
    print("Final Model: ")

    best_net.eval()
    best_net.evaluate_architecture(test_x, test_y)

    # Set classifier for Model
    MyPricing_Model.base_classifier = best_net
    

    # If not calculating from beginning

    ####################
    #print(MyPricing_Model.base_classifier)
    # Calculate probabilities and prices
    """







