# -*- coding: utf-8 -*-
"""
Static spectra data class, child of Exp
"""
from .exp import Exp

__all__ = ['Static']


class Static(Exp):
    '''
    Static experiments class
    '''
    def __init__(self, dir_save):
        super().__init__(dir_save)
        self.info = f'Class instance of {self.__class__}'
        self.path = None
        print(self.info)
