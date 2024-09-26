import json


class AttoException(Exception):
    def __init__(self, error_text=None, error_number=0):
        self.errorText = error_text
        self.errorNumber = error_number


class AttoResult:
    def __init__(self, result_dict):
        self.resultDict = result_dict

    def __getitem__(self, index):
        if "error" in self.resultDict:
            raise AttoException("JSON error in %s" % self.resultDict['error'])
        result_list = self.resultDict.get("result", [])
        if len(result_list) <= index:
            raise AttoException(error_text="Unknown error occurred", error_number=-1)
        return result_list[index]

    def __repr__(self):
        return json.dumps(self.resultDict)

    def __str__(self):
        return self.__repr__()
