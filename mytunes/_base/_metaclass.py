# Solution from http://www.phyast.pitt.edu/~micheles/python/metatype.html

meta_dic = {}


def _is_trivial(base: type, metas) -> bool:
    return sum([issubclass(meta, base) for meta in metas], base is type)


def _generate_metaclass(bases, metas, name: str = None, priority: bool = False):
    # hackish!! m is trivial if it is 'type' or, in the case explicit
    # metaclasses are given, if it is a superclass of at least one of them
    others = tuple([mb for mb in map(type, bases) if not _is_trivial(mb, metas)])
    metabases = (others + metas, metas + others)[priority]
    if metabases in meta_dic:  # already generated metaclass
        return meta_dic[metabases]
    elif not metabases:  # trivial metabase
        meta = type
    elif len(metabases) == 1:  # single metabase
        meta = metabases[0]
    else:  # multiple metabases
        metaname = name or "_" + ''.join([m.__name__ for m in metabases])
        meta = make_cls()(metaname, metabases, {})
    return meta_dic.setdefault(metabases, meta)


def make_cls(*metas, **options):
    """Class factory avoiding metatype conflicts. The invocation syntax is
    make_cls(M1,M2,..,priority=1)(name,bases,dic). If the base classes have
    metaclasses conflicting within themselves or with the given metaclasses,
    it automatically generates a compatible metaclass and instantiate it.
    If priority is True, the given metaclasses have priority over the
    bases' metaclasses"""
    name = options.get('name', None)  # default, generate name from metaclasses
    priority = options.get('priority', False)  # default, no priority

    def _make_metaclass(cls_name, bases, namespace, **kwargs):
        bases_deduplicated = []
        for base in bases:
            if base in bases_deduplicated:
                continue
            if any(issubclass(b, base) for b in bases if b is not base):
                continue
            bases_deduplicated.append(base)

        bases = tuple(bases_deduplicated)
        metaclass = _generate_metaclass(bases, metas, name=name or f"{cls_name}Metaclass", priority=priority)
        return metaclass(cls_name, bases, namespace, **kwargs)

    return _make_metaclass
