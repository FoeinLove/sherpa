import pandas as pd
import numpy as np
import os
import pickle as pkl
import abc

class AbstractResultsTable(object):
    ''' 
    Required methods for MainLoop.
    Additional functionality may be useful for different Algorithms.
    '''
    def __init__(self, dir='./', loss='loss'):
        '''
        dir  = csv file saved to dir/results.csv.
        loss = Key for channel to minimize (history[loss]). 
        '''
        self.dir = dir
        self.csv_path= os.path.join(dir, 'results.csv')
        self.loss = loss

        try:
            os.makedirs(dir)  # os.makedirs(os.path.dirname(self.dir))
        except:
            pass
        return      
   
    def update(self, index, historyfile, hp=None):
        ''' Update results table. Called by MainLoop. '''
        with open(historyfile, 'rb') as f:
            history = pkl.load(f)
        lowest_loss   = min(history[self.loss])
        epochs_seen   = len(history[self.loss])
        self._set(index=index, loss=lowest_loss, epochs=epochs_seen, hp=hp, historyfile=historyfile)
        return
    
    @abc.abstractmethod
    def get_best(self):
        ''' Return best id, loss value, hp, historyfile. '''
        pass
    
    @abc.abstractmethod
    def _set(self, index, loss, epochs_seen, hp, historyfile):
        ''' Set values in results table. Not called '''
        pass
    
class ResultsTable(AbstractResultsTable):
    """
    Handles input/output of an underlying hard-disk stored .csv that stores the results.
    ID     = Unique ID for each model instantiation.
    Loss   = Current loss value.
    Epochs = Number of training epochs.
    Repeat = Is this model a repeat of another model. 
    HP     = Dictionary of hyperparameters.
    """
    def __init__(self, dir='./', loss='loss', overwrite=False):
        super(ResultsTable, self).__init__(dir=dir, loss=loss)
        #self.dtype= collections.OrderedDict({'ID':np.int32, 'Loss':np.float64, 'Epochs':np.int32, 'HP':np.dtype('U'), 'History':np.dtype('U')})
        self.keys = ('ID', 'Loss', 'Epochs', 'HP', 'History')
        #self.keys = list(self.dtype.keys())
        if overwrite or not os.path.isfile(self.csv_path):
            self._create_table()
        else:
            self._load_table()
        return
    
    def _create_table(self):
        ''' Creates new table and saves it to disk.'''
        self.df = pd.DataFrame(columns=self.keys, )
        self._save()
        
    def _load_table(self):
        '''
        Loads table from disk and returns it.
        # Returns: pandas df
        '''
        try:
            self.df = pd.read_csv(self.csv_path)
        except:
            print('Unable to read existing csv file at {} using pandas'.format(self.csv_path))
            raise
 
    def _save(self):
        """
        Updates stored csv
        """
        self.df.to_csv(self.csv_path)
       
    def _set(self, index, loss, epochs, hp=None, historyfile=None):
        """
        Sets a value for a model using index as identifier and saves the hyperparameter description of it. 
        index = Unique identifier for each model instantiation. Used to identify models that are paused/restarted.
        loss  = loss value.
        epochs = Total number of epochs that the model has been trained.
        historyfile = File path.    
        """
        import collections
        if index in self.df.index:
            # Update previous result.
            self.df.set_value(index=index, col='Loss', value=loss)
            self.df.set_value(index=index, col='Epochs', value=epochs)
        else:
            # New line.
            #new_line = pd.DataFrame(collections.OrderedDict(zip(self.keys, (int(index), loss, int(epochs), hp, historyfile))),
            #                        index=[index])
            new_line = pd.DataFrame([[index, loss, epochs, hp, historyfile]], index=[index], columns=self.keys)
            self.df = self.df.append(new_line)
        self._save()
    
    def get_k_lowest(self, k):
        """
        Gets the k models with lowest global loss.

        # Args:
             k: Integer, number of id's to return

        # Returns:
             list with model ids

        TODO: add more options, e.g. ignore repeats.
        """
        df_sorted = self.df.sort_values(by='Loss', ascending=True)
        data = df_sorted.iloc[0:k]
        return data 

    def get_best(self):
        ''' Return values for best model so far.'''    
        data = self.get_k_lowest(k=1)
        bestdict = dict(zip(self.keys, [data[k].iloc[0] for k in self.keys]))
        return bestdict
    

class ResultsTableOld(AbstractResultsTable):
    """
    DEPRECATED
    
    Handles input/output of an underlying hard-disk stored .csv that stores the results
    """
    def __init__(self, dir='./', loss='loss', overwrite=False):
        super(ResultsTable, self).__init__(dir=dir, loss=loss)
        self.keys = ('Run', 'ID', 'Hparams', 'Loss', 'Epochs')
        if overwrite:
            df = self._create_table()
            self._save(df)
        return

    def get_k_lowest_from_run(self, k, run):
        """
        Gets the k models with lowest loss from a specific run. Note this is not necesarily the global minimum
        
        # Args:
            k: Integer, number of id's to return
            run: Integer, refers to hyper-band run

        # Returns:
            list of id's from this run
        """
        df = self.get_table()
        df_run = df[df['Run'] == run]
        sorted_df_run = df_run.sort_values(by='Loss', ascending=True)
        return list(sorted_df_run.index[0:k])

    def sample_k_ids_from_run(self, k, run, temperature=1.):
        """
        Samples k models with  probability proportional to inverse loss
        from a specific run. Note this is not necesarily the global minimum

        # Args:
            k: Integer, number of id's to return
            run: Integer, refers to hyper-band run

        # Returns:
            list of id's from this run
        """
        df = self.get_table()
        df_run = df[df['Run'] == run]
        # p = 1/df_run['Loss']
        p = np.exp(-df_run['Loss']/temperature)
        sampled_ids = np.random.choice(df_run.index, size=k, replace=False,
                                       p=p/np.sum(p))
        return list(sampled_ids)


    def get_k_lowest(self, k):
        """
        Gets the k models with lowest global loss.

        # Args:
             k: Integer, number of id's to return

        # Returns:
             list with run-id strings to identify models 
        """
        df = self.get_table()
        sorted_df_run = df.sort_values(by='Loss', ascending=True)
        ids = list(sorted_df_run['ID'][0:k])
        runs = list(sorted_df_run['Run'][0:k])
        id_run = []
        for row_id in zip(ids, runs):
            id_run.append(self._get_idx(row_id[0], row_id[1]))
        return id_run

    def set(self, run_id, loss, epochs, hp=None):
        """
        Sets a value for a model using (run, id) as identifier and saves the hyperparameter description of it. 
        
        # Args:
            run_id: Tuple, contains run and id numbers
            loss: float, e.g. validation loss value to set in table
            hp:


        """
        df = self.get_table()
        run, id = [int(num) for num in run_id.split('_')]
        if hp:
            new_line = pd.DataFrame({key: [val] for key, val in zip(self.keys, (run, id, hp, loss, epochs))},
                                    index=[run_id])
            df = df.append(new_line)
        else:
            df.set_value(index=run_id, col='Loss', value=loss)
            df.set_value(index=run_id, col='Epochs', value=epochs)
        self._save(df)

    def set_value(self, run_id, col, value):
        df = self.get_table()
        df.set_value(index=run_id, col=col, value=value)
        self._save(df)

    def _get_idx(self, run, id):
        """
        Returns the run, id in a string with the format to be used in the table
        
        # Args 
            run: Integer, run number
            id: Integer, id number within the run

        # Returns:
           String with correct format for identification
        """
        return '{}_{}'.format(run, id)

    def _create_table(self):
        """
        Initializes a pandas dataframe with the set of keys of this object
        
        # Returns: 
            pandas dataframe

        """
        return pd.DataFrame(columns=self.keys)

    def get_table(self):
        """
        Loads table from disk and returns it.
        # Returns: pandas df

        """
        return pd.read_csv(self.csv_path, index_col=0, dtype={'Run': np.int32,
                                                     'Epochs': np.int32,
                                                     'ID': np.int32,
                                                     'Loss': np.float64,
                                                     'Hparams': np.dtype('U')})

    def get(self, run_id, parameter=None):
        """
        Returns parameter value of a model from the table
        Args:
            run_id: tuple, (run, id)
            parameter: string, name of the parameter to be returned

        Returns: validation loss 

        """
        df = self.get_table()
        assert parameter is not None, "you must specify a parameter to get" \
                                      "from the resultstable keys"
        assert parameter in self.keys, \
            'parameter must match with one of the keys of resultstable,' \
            'found {}'.format(parameter)
        return df.ix[run_id][parameter]

    def _save(self, df):
        """
        Updates stored csv
        # Args:
            df: dataframe

        """
        df.to_csv(self.csv_path)

    def get_hp_df(self, as_design_matrix=False):
        df = self.get_table()
        hparam_df = pd.DataFrame([eval(item) for item in df['Hparams']])
        return hparam_df if not as_design_matrix or hparam_df.empty else \
            pd.get_dummies(hparam_df, drop_first=True)

    def get_column(self, key='Loss'):
        df = self.get_table()
        return df[key]
