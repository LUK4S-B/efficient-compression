"""
Class to load and process the Wiki-40B dataset from TensorFlow Datasets, and save it as a PyTorch Dataset.
See end of file for usage example.

The dataset is either loaded if it already exists locally or created and saved to a file when 
the load_dataset method is being called.
--> The dataset can also be build by running this file as a script (recommended). <--
"""
import torch
from torch.utils.data import Dataset
import tensorflow_datasets as tfds
import tensorflow as tf
import numpy as np
import os
from tqdm import tqdm
import copy


class ByteWikipediaDataset(Dataset):
    """PyTorch Dataset for byte-level Wikipedia data.
    
    This dataset stores Wikipedia text as byte sequences and provides access to these
    sequences through the standard PyTorch Dataset interface.
    """
    
    def __init__(self, data, split):
        """Initialize the ByteWikipediaDataset.
        
        Args:
            data: List of byte sequences representing text chunks
            split: String identifier for the dataset split ('train', 'validation', or 'test')
        """
        self.data = data
        self.split = split
        
    def __len__(self):
        """Return the number of sequences in the dataset."""
        return len(self.data)
        
    def __getitem__(self, idx):
        """Retrieve and convert the sequence at the given index.
        
        Args:
            idx: Index of the sequence to retrieve
            
        Returns:
            torch.Tensor: Long tensor containing the byte sequence
        """
        seq = np.frombuffer(self.data[idx], dtype=np.uint8).copy()
        return torch.from_numpy(seq).long()


class WikipediaDatasets:
    """Container class for all Wikipedia dataset splits with utility methods.
    
    Provides functionality to create, save, load, and extract subsets from 
    Wikipedia datasets at the byte level.
    """
    
    def __init__(self, train, validation, test, sequence_length):
        """Initialize WikipediaDatasets with all three standard splits.
        
        Args:
            train: ByteWikipediaDataset for training
            validation: ByteWikipediaDataset for validation
            test: ByteWikipediaDataset for testing
            sequence_length: Length of each sequence in the datasets
        """
        self.train = train
        self.validation = validation
        self.test = test
        self.sequence_length = sequence_length
    
    @classmethod
    def create_and_save_dataset(cls, sequence_length, save_path):
        """Create datasets from Wiki-40B and save them to disk.
        
        Loads the original Wiki-40B dataset, processes it into fixed-length byte sequences,
        and saves the resulting datasets to the specified path.
        
        Args:
            sequence_length: Length of each sequence in the datasets
            save_path: File path where the processed datasets will be saved
            
        Returns:
            WikipediaDatasets: Object containing all three dataset splits
        """
        print("Loading Wiki-40B dataset from tensorflow-datasets...")
        wiki_data = tfds.load('wiki40b/en', split=['train', 'validation', 'test'])
        print("Wiki-40B dataset loaded successfully.")
        
        # Get the total number of examples for each split
        total_examples = {split: data.cardinality().numpy() for split, data in zip(['train', 'validation', 'test'], wiki_data)}
        for split, count in total_examples.items():
            if count == tf.data.UNKNOWN_CARDINALITY:
                print(f"{split} dataset cardinality unknown. Progress bar may be inaccurate.")
                total_examples[split] = None  # tqdm will show ? instead of total
                
        processed_data = {split: [] for split in ['train', 'validation', 'test']}
        print("Processing and saving dataset...")
        
        for split, data in zip(['train', 'validation', 'test'], wiki_data):
            current_chunk = b''
            with tqdm(total=total_examples[split], desc=f"Processing {split} examples", unit="example") as pbar:
                for example in data:
                    text = example['text'].numpy().decode('utf-8')
                    byte_encoded = text.encode('utf-8')
                    current_chunk += byte_encoded
                    
                    while len(current_chunk) >= sequence_length:
                        chunk, current_chunk = current_chunk[:sequence_length], current_chunk[sequence_length:]
                        processed_data[split].append(chunk)  # Store as bytes
                    pbar.update(1)
                    
            # Handle the last chunk
            if current_chunk:
                if len(current_chunk) < sequence_length:
                    current_chunk = current_chunk + b'\0' * (sequence_length - len(current_chunk))
                processed_data[split].append(current_chunk[:sequence_length])  # Store as bytes
                
        datasets = WikipediaDatasets(
            train=ByteWikipediaDataset(processed_data['train'], 'train'),
            validation=ByteWikipediaDataset(processed_data['validation'], 'validation'),
            test=ByteWikipediaDataset(processed_data['test'], 'test'),
            sequence_length=sequence_length
        )
        
        print(f"Saving processed dataset to {save_path}")
        torch.save(datasets, save_path)
        print("Dataset saved successfully.")
        return datasets
        
    @classmethod
    def load_dataset(cls, load_path, required_seq_length):
        """Load datasets from disk or create them if not available.
        
        Attempts to load datasets from the specified path. If the file doesn't exist
        or the sequence length doesn't match, creates new datasets with the required length.
        
        Args:
            load_path: File path from which to load the processed datasets
            required_seq_length: Required sequence length for the datasets
            
        Returns:
            WikipediaDatasets: Object containing all three dataset splits
        """
        if not os.path.exists(load_path):
            print(f"Dataset not found at {load_path} Creating a new dataset file...")
            return cls.create_and_save_dataset(required_seq_length, load_path)
            
        print(f"Loading dataset from {load_path}")
        datasets = torch.load(load_path)
        
        if datasets.sequence_length != required_seq_length:
            print(f"Warning: Loaded dataset has sequence length {datasets.sequence_length}, "
                  f"but {required_seq_length} was requested.")
            print("Creating a new dataset with the correct sequence length...")
            datasets = cls.create_and_save_dataset(required_seq_length, load_path)
        else:
            print("Dataset loaded successfully.")
            
        return datasets
        
    @staticmethod
    def get_subset(start_token: int, end_token: int, dataset: ByteWikipediaDataset) -> ByteWikipediaDataset:
        """Extract a subset of the dataset based on token indices.
        
        Creates a new dataset containing only the chunks between the specified token indices.
        Both indices must be multiples of the sequence length.
        
        Args:
            start_token: Starting token index (must be a multiple of sequence length)
            end_token: Ending token index (must be a multiple of sequence length)
            dataset: Source dataset from which to extract the subset
            
        Returns:
            ByteWikipediaDataset: New dataset containing only the specified subset
            
        Raises:
            AssertionError: If start_token or end_token are not multiples of sequence length,
                or if start_token is not smaller than end_token
        """
        sequence_length = len(dataset.data[0])
        assert start_token % sequence_length == 0, f"Start token must be a multiple of the sequence length {sequence_length}"
        assert end_token % sequence_length == 0, f"End token must be a multiple of the sequence length {sequence_length}"
        assert start_token < end_token, "Start token must be smaller than end token"
        
        start_chunk = start_token // sequence_length
        end_chunk = end_token // sequence_length
        subset = copy.deepcopy(dataset)
        subset.data = subset.data[start_chunk:end_chunk]
        return subset


# Usage example:
if __name__ == "__main__":
    import os
    SEQ_LENGTH = 2048
    SAVE_DIR = os.getcwd()  # Use the current working directory
    SAVE_PATH = os.path.join(SAVE_DIR, 'processed_wiki_dataset.pt')
    
    if not os.path.exists(SAVE_PATH):
        datasets = WikipediaDatasets.create_and_save_dataset(SEQ_LENGTH, SAVE_PATH)
    else:
        datasets = WikipediaDatasets.load_dataset(SAVE_PATH, SEQ_LENGTH)
        
    print(f"Train dataset contains {len(datasets.train)} chunks")
    print(f"Validation dataset contains {len(datasets.validation)} chunks")
    print(f"Test dataset contains {len(datasets.test)} chunks")
    
    # Test the dataset
    print("Testing the first example of each split:")
    for split in ['train', 'validation', 'test']:
        dataset = getattr(datasets, split)
        first_example = dataset[0]
        print(f"Shape of first {split} example: {first_example.shape}")
        print(f"First 100 bytes of {split}: {first_example[:100]}")
        
    # Get a subset of the dataset, e.g. the first 15MB of the training set
    train_set = datasets.train
    first_15mb = WikipediaDatasets.get_subset(0, int(15e6 // 2048 * 2048), train_set)
    print(f"Train dataset contains {len(train_set.data)} chunks")
    print(f"First 15MB of training set contains {len(first_15mb.data)} chunks")
    
    # Example of using with DataLoader
    from torch.utils.data import DataLoader
    dataloaders = {
        'train': DataLoader(datasets.train, batch_size=32, shuffle=True),
        'validation': DataLoader(datasets.validation, batch_size=32, shuffle=False),
        'test': DataLoader(datasets.test, batch_size=32, shuffle=False)
    }
    
    for split, dataloader in dataloaders.items():
        for batch in dataloader:
            print(f"{split} batch shape: {batch.shape}")
            break  # Just print the first batch and stop