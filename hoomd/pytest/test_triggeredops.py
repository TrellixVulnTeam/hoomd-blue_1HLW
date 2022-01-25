# Copyright (c) 2009-2022 The Regents of the University of Michigan.
# Part of HOOMD-blue, released under the BSD 3-Clause License.

from hoomd.pytest.dummy import DummyCppObj, DummySimulation, DummyTrigger
from hoomd.pytest.dummy import DummyTriggeredOp
from hoomd.data.syncedlist import SyncedList
from hoomd.trigger import Periodic


def test_initialization():
    triggered_op = DummyTriggeredOp(trigger=1)
    assert type(triggered_op.trigger) == Periodic
    assert triggered_op.trigger.period == 1
    assert triggered_op.trigger.phase == 0


def test_custom_initialization():
    triggered_op = DummyTriggeredOp(trigger=DummyTrigger())
    assert type(triggered_op.trigger) == DummyTrigger
    assert triggered_op.trigger(4)


def test_trigger_resetting():
    triggered_op = DummyTriggeredOp(trigger=3)
    triggered_op.trigger = DummyTrigger()
    assert type(triggered_op.trigger) == DummyTrigger
    assert triggered_op.trigger(4)


def test_attach():
    triggered_op = DummyTriggeredOp(trigger=1)
    sim = DummySimulation()
    slist = SyncedList(lambda x: isinstance(x, DummyTriggeredOp), lambda x:
                       (x._cpp_obj, x.trigger))
    slist.append(triggered_op)
    triggered_op._cpp_obj = DummyCppObj()
    slist._sync(sim, sim._cpp_sys.dummy_list)
    assert len(sim._cpp_sys.dummy_list) == 1
    assert len(sim._cpp_sys.dummy_list[0]) == 2
    assert triggered_op._cpp_obj == sim._cpp_sys.dummy_list[0][0]
    assert triggered_op.trigger == sim._cpp_sys.dummy_list[0][1]


def test_attach_trigger_resetting():
    triggered_op = DummyTriggeredOp(trigger=1)
    sim = DummySimulation()
    slist = SyncedList(lambda x: isinstance(x, DummyTriggeredOp), lambda x:
                       (x._cpp_obj, x.trigger))
    slist.append(triggered_op)
    slist._sync(sim, sim._cpp_sys.dummy_list)
    triggered_op.trigger = DummyTrigger()
    assert len(sim._cpp_sys.dummy_list) == 1
    assert len(sim._cpp_sys.dummy_list[0]) == 2
    assert triggered_op._cpp_obj == sim._cpp_sys.dummy_list[0][0]
    assert triggered_op.trigger == sim._cpp_sys.dummy_list[0][1]
    assert type(triggered_op.trigger) == DummyTrigger
