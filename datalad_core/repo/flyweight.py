import threading
from abc import abstractmethod
from pathlib import Path


class PathBasedFlyweight(type):
    """Metaclass for a path-based flyweight pattern

    See `https://en.wikipedia.org/wiki/Flyweight_pattern`_ for information
    on the pattern.

    There is a companion class :class:`Flyweighted`, which can be used as
    a base class for classes implementing this pattern.

    This implementation integrates the "factory" into the actual classes.
    Consuming code generally need not be aware of the flyweight pattern.

    To use this pattern, add this class as a metaclass to the class it shall
    be used with. Additionally there needs to be a class attribute
    `_unique_instances`, which should be a `WeakValueDictionary`.
    """

    # to avoid parallel creation of (identical) instances
    _lock = threading.Lock()

    # ATM the implementation relies on the fact that the only
    # constructor argument to determine the identity of
    # a flyweighted entity is a `path`. As soon as we need
    # to add to this set of argument, this (or a derived)
    # implementation must be amended to ensure that we can
    # correctly tell if and when an instance can be treated
    # as "same"
    def __call__(cls, path: Path):
        id_ = path.absolute()

        # Thread lock following block so we do not fall victim to race
        # condition across threads trying to instantiate multiple instances. In
        # principle we better have a lock per id_ but that mean we might race
        # at getting "name specific lock" (Yarik did not research much), so
        # keeping it KISS -- just lock instantiation altogether, but could be
        # made smarter later on.
        with cls._lock:
            # ignore typing, because MIH does not know how to say that
            # `cls` is required to have a particular class attribute
            instance = cls._unique_instances.get(id_, None)  # type: ignore
            if instance is None or not instance.flyweight_valid():
                # we have no such instance yet or the existing one is
                # invalidated, so we instantiate.
                # Importantly, we take any args at face-value and do not
                # let generic code fiddle with them to preserve any and
                # all semantics of the instantiated class
                instance = type.__call__(cls, path)
                # ignore typing, because MIH does not know how to say that
                # `cls` is required to have a particular class attribute
                cls._unique_instances[id_] = instance  # type: ignore

        return instance


class Flyweighted:
    def __hash__(self):
        # the flyweight key is already determining unique instances
        # add the class name to distinguish from strings of a path
        return hash((self.__class__.__name__, self.__weakref__.key))

    @classmethod
    def _close(cls, path):
        """Finalize/clean-up when a flyweighted instance is garbage-collected

        This default implementation does nothing.

        This is a classmethod and not an instance method, and we also cannot
        accept any `self`-type arguments. This would create an additional
        reference to the object and thereby preventing it from being collected
        at all.
        """

    @abstractmethod
    def flyweight_valid(self):
        """Tests a cached instance whether it continues to be good to reuse

        This test runs on every object creation and should be kept as cheap as
        possible.
        """
