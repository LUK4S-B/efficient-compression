import time
import torch
from torch.nn.parameter import Parameter
from torch.optim import Optimizer
from torch.utils.data import DataLoader
from torch.nn.parallel import DistributedDataParallel as DDP
from typing import Dict, Any, Union
from src.CheckpointHandler import CheckpointHandler
from src.DistributedOptimizationProcedures.BaseProcedure import ProcedureTrainer, get_optimization_procedure

class DrrTrainer(ProcedureTrainer):
    """Trainer implementing Differentiable Relaxation of ℓ₀-Regularization (DRR) strategy for sparse neural network training.
    
    DRR applies a continuous approximation of the L0 norm to enable gradient-based
    sparsification during training.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize DRR trainer with alpha and beta hyperparameters.
        
        Args:
            *args: Positional arguments passed to parent class
            **kwargs: Keyword arguments passed to parent class
        """
        super().__init__(*args, **kwargs)
        assert isinstance(self.args["beta"], float), "beta must be a float"
        self.alpha = self.args["alpha"]
        self.beta = self.args["beta"]

    # Overrides the parent class method
    def modify_grads(self):
        """Apply DRR gradient modification to all model parameters.
        
        Implements the DRR regularization across the entire model.
        """
        for param in self.ddp_model.parameters():
            self.modify_grad(param)
            
    def modify_grad(self, param):
        """Apply DRR gradient modification to a single parameter.
        
        Adds a regularization term based on exponential decay to promote sparsity.
        
        Args:
            param: Parameter to modify gradients for
        """
        if torch.is_tensor(param.grad):
            param.grad += self.alpha * self.beta * torch.sign(param.data) * torch.exp( - self.beta * torch.abs(param.data))

def drr_procedure(
    ddp_model: DDP,
    optimizer: Optimizer,
    logs: Dict[str, Any],
    distributed_trainer,
    dataloader_train: DataLoader,
    val_dataset,
    checkpointer: CheckpointHandler,
    args: Dict[str, Any],
):
    """Execute the DRR optimization procedure with pruning and fine-tuning phases.
    
    Args:
        ddp_model: Distributed model to train
        optimizer: Optimizer for parameter updates
        logs: Dictionary for tracking metrics
        distributed_trainer: Trainer managing distributed operations
        dataloader_train: Data provider for training
        val_dataset: Dataset for validation during pruning
        checkpointer: Handler for saving model state
        args: Configuration parameters
    
    Returns:
        tuple: (trained ddp_model, optimizer, logs, args)
    """
    return get_optimization_procedure(DrrTrainer, ddp_model, optimizer, logs, distributed_trainer, dataloader_train, val_dataset, checkpointer, args)