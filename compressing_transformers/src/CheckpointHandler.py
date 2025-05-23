import os
import pickle
import time

class CheckpointHandler:
    """Manages model checkpointing with runtime-based saving and restoration."""

    def __init__(self, experiment_name, checkpoint_every, max_runtime, checkpoint_dir=None):
        """Initialize checkpoint handler with configuration parameters.

        Args:
            experiment_name: Name of the experiment for checkpoint file naming.
            checkpoint_every: Time interval in seconds between checkpoint checks.
            max_runtime: Maximum allowed runtime in seconds before enforced checkpointing.
            checkpoint_dir: Directory to store checkpoints. Defaults to script directory.
        """
        self.experiment_name = experiment_name
        self.checkpoint_dir = checkpoint_dir or os.path.dirname(os.path.abspath(__file__))
        self.checkpoint_path = os.path.join(self.checkpoint_dir, f"{experiment_name}_checkpoint.pkl")
        self.epoch = 0
        self.chunk = 0
        self.start_time = time.time()
        self.last_check_time = self.start_time
        self.checkpoint_every = checkpoint_every
        self.max_runtime = max_runtime

    def save_checkpoint(self, ddp_model, optimizer, logs):
        """Save model state, optimizer state, and training logs to checkpoint file.
        
        Args:
            ddp_model: DistributedDataParallel model to checkpoint.
            optimizer: Optimizer whose state will be saved.
            logs: Dictionary containing training metrics and history.
        """
        checkpoint = {
            'epoch': self.epoch,
            'chunk': self.chunk,
            'model_state_dict': ddp_model.module.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'logs': logs
        }
        with open(self.checkpoint_path, 'wb') as f:
            pickle.dump(checkpoint, f)

    def load_checkpoint(self):
        """Load checkpoint if available or initialize fresh training state.
        
        Returns:
            tuple: (model_state_dict, optimizer_state_dict, logs) if checkpoint exists,
            or (None, None, initialized_logs) if no checkpoint found.
        """
        if os.path.exists(self.checkpoint_path):
            with open(self.checkpoint_path, 'rb') as f:
                checkpoint = pickle.load(f)
            self.epoch = checkpoint['epoch']
            self.chunk = checkpoint['chunk']
            print(f"Loaded checkpoint from epoch {self.epoch}, chunk {self.chunk}")
            return checkpoint['model_state_dict'], checkpoint['optimizer_state_dict'], checkpoint['logs']
        else:
            print("No checkpoint found, starting from the beginning")
            return None, None, initialize_logs()

    def update(self, epoch, chunk):
        """Update internal epoch and chunk counters.
        
        Args:
            epoch: Current training epoch number.
            chunk: Current data chunk number within the epoch.
        """
        self.epoch = epoch
        self.chunk = chunk

    def should_checkpoint(self):
        """Determine if checkpointing should occur based on time intervals.
        
        Returns:
            bool: True if max runtime exceeded or checkpoint interval reached.
        """
        current_time = time.time()
        if current_time - self.last_check_time > self.checkpoint_every:
            self.last_check_time = current_time
            if current_time - self.start_time > self.max_runtime:
                return True
        return False


def initialize_logs():
    """Create empty log dictionary with required tracking metrics.
    
    Returns:
        dict: Dictionary with empty lists for all training metrics.
    """
    return {
        "train_loss": [], "train_loss_X": [], "train_loss_X_epoch": [], 
        "runtime_per_250_batches": [], "l0_norm": [], "l0_norm_X": [], 
        "l0_norm_X_epoch": []
    }