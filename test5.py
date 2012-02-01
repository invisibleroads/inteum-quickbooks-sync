'Update customers'
from itertools import izip


def synchronize(requestProcessor, itemName, requestFields, allPacks):
    'Find existing data and add new data'
    requestName = itemName + 'Query'
    newPacks = get_new(requestProcessor, requestName, requestFields, allPacks)
    if not newPacks:
        return
    for onePack in newPacks:
        print onePack
    if raw_input('Proceed (y/[n])? ').lower() != 'y':
        return
    requestName = itemName + 'Add'
    return add_new(requestProcessor, requestName, requestFields, newPacks)


def get_new(requestProcessor, requestName, requestFields, allPacks):
    'Get new data'
    oldPacks = []
    for result in requestProcessor.call(requestName + 'Rq', {}):
        oldPacks.append(tuple(result.get(x) for x in requestFields))
    return set(map(tuple, allPacks)).difference(oldPacks)


def add_new(requestProcessor, requestName, requestFields, newPacks):
    'Add new data'
    for onePack in newPacks:
        print requestProcessor.call(requestName + 'Rq', {
            requestName: dict(izip(requestFields, onePack))
        })
