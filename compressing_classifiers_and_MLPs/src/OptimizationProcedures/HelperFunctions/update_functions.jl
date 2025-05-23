using Lux, Accessors, Revise
include("recursive_operations.jl")

# The update functions partly employ julia's Lux library for backpropagation of gradients and partly compute gradients explicitly depending on the regularization scheme of the loss function (for increased efficiency).
# The loss functions handed to the update_state! functions are structs and julia's multiple dispatch then decides, depending on the struct type, which update_state! is called.

function update_state!(vjp::Lux.AbstractADType, loss_fun::GenericLossFunction, batch, tstate::Lux.Training.TrainState)
    grads, loss, _, tstate = Training.compute_gradients(vjp, loss_fun, batch, tstate)
    tstate = Training.apply_gradients!(tstate, grads)
    return tstate, loss, nothing
end


function update_state!(vjp::Lux.AbstractADType, loss_fun::Union{PMMP, PMMP_Gauss}, batch, tstate::Lux.Training.TrainState)
    grads, loss, _, tstate = Training.compute_gradients(vjp, loss_fun, batch, tstate)
    if loss_fun.rho != 0
        recursively_modify!(grads.p, tstate.parameters.p, loss_fun, loss_fun.fun_L2)
    end
    if loss_fun.L1_alpha != 0
        recursively_modify!(grads.p, tstate.parameters.p, loss_fun, loss_fun.fun1)
    end
    if loss_fun.alpha != 0
        recursively_modify_PMMP!(grads.p, tstate.parameters.p, tstate.parameters.pw, tstate.parameters.pp, tstate.parameters.u, loss_fun.grad_template.p, loss_fun.grad_template.pw, loss_fun.grad_template.pp, loss_fun.grad_template.u, loss_fun, loss_fun.fun_p, loss_fun.fun_pw, loss_fun.fun_pp, loss_fun.fun_u)
        if haskey(loss_fun.grad_template, :sigma)
            loss_fun.grad_template.sigma .= grads.sigma
        end
        tstate = Training.apply_gradients!(tstate, loss_fun.grad_template)
        project_params!(tstate.parameters.pp)
    else
        tstate = Training.apply_gradients!(tstate, grads)
    end
    return tstate, loss, nothing
end


function update_state!(vjp::Lux.AbstractADType, loss_fun::RL1_loss, batch, tstate::Lux.Training.TrainState)
    grads, loss, _, tstate = Training.compute_gradients(vjp, loss_fun, batch, tstate)
    if loss_fun.alpha != 0
        recursively_modify!(grads, tstate.parameters, loss_fun, loss_fun.fun1)
    end
    if loss_fun.rho != 0
        recursively_modify!(grads, tstate.parameters, loss_fun, loss_fun.fun2)
    end
    tstate = Training.apply_gradients!(tstate, grads)
    return tstate, loss, nothing
end

function update_state!(vjp::Lux.AbstractADType, loss_fun::RL1_Gauss, batch, tstate::Lux.Training.TrainState)
    grads, loss, _, tstate = Training.compute_gradients(vjp, loss_fun, batch, tstate)
    if loss_fun.alpha != 0
        for (l1,l2) in zip(grads.p, tstate.parameters.p)
            for (w1,w2) in zip(l1,l2)
                w1 .+= loss_fun.alpha .* sign.(w2)
            end
        end
    end
    if loss_fun.rho != 0
        for (l1,l2) in zip(grads.p, tstate.parameters.p)
            l1.weight .+= loss_fun.rho .* 2 .* l2.weight
            l1.bias .+= loss_fun.rho .* 2 .* l2.bias
        end
    end
    tstate = Training.apply_gradients!(tstate, grads)
    return tstate, loss, nothing
end

function update_state!(vjp::Lux.AbstractADType, loss_fun::DRR, batch, tstate::Lux.Training.TrainState)
    grads, loss, _, tstate = Training.compute_gradients(vjp, loss_fun, batch, tstate)
    if loss_fun.alpha != 0
        recursively_modify_DRR!(grads, tstate.parameters, loss_fun, loss_fun.fun1)
    end
    if loss_fun.rho != 0
        recursively_modify!(grads, tstate.parameters, loss_fun, loss_fun.fun2)
    end
    tstate = Training.apply_gradients!(tstate, grads)
    return tstate, loss, nothing
end

function update_state!(vjp::Lux.AbstractADType, loss_fun::DRR_Gauss, batch, tstate::Lux.Training.TrainState)
    grads, loss, _, tstate = Training.compute_gradients(vjp, loss_fun, batch, tstate)

    if loss_fun.alpha != 0
        if loss_fun.NORM
            for (l1,l2) in zip(grads.p, tstate.parameters.p)
                for (w1,w2) in zip(l1,l2)
                    scaling_factor = Lux.parameterlength(tstate.model) / Lux.parameterlength(tstate.model[layer_name]) / length(tstate.model)
                    w1 .+= loss_fun.alpha .* sign.(w2) .* loss_fun.beta .* exp.(- loss_fun.beta .* abs.(w2)) .* scaling_factor
                end
            end
        else
            for (l1,l2) in zip(grads.p, tstate.parameters.p)
                for (w1,w2) in zip(l1,l2)
                    w1 .+= loss_fun.alpha .* sign.(w2) .* loss_fun.beta .* exp.(- loss_fun.beta .* abs.(w2))
                end
            end
        end
    end
    if loss_fun.rho != 0
        for (l1,l2) in zip(grads.p, tstate.parameters.p)
            for (w1,w2) in zip(l1,l2)
                w1 .+= loss_fun.rho .* 2 .* w2
            end
        end
    end
    tstate = Training.apply_gradients!(tstate, grads)
    return tstate, loss, nothing
end
