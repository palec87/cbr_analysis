# -*- coding: utf-8 -*-
"""
Created on Fri Jun  5 21:02:16 2020

@author: David Palecek
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import scipy.optimize as optim
from scipy.integrate import solve_ivp, odeint
# TODO, load fitting module
from ..helpers import support as sup
from ..helpers.support import refresh_vals
from ..modules import plotting as plot
from .. modules import fitting as ft

from .exp import Exp

__all__ = ['Trs']


class Trs(Exp):
    '''
    Time-resolved-spectroscopy class
    TODO: Fitting here
    '''
    def __init__(self, dir_save=None):
        super().__init__(dir_save)
        self.info = f'Class instance of {self.__class__}'
        self.path = None
        self._t = None
        self.t0 = 0
        self.t_unit = None
        self.wl = None
        self.wl_unit = None
        # kinetics, spectra
        self.kin = None
        self.kin_rng = None
        self.spe = None
        self.spe_rng = None
        self.tmax_id = None
        self.tmin_id = None
        self.wlmax_id = None
        self.wlmin_id = None
        # sweeps attributes
        self.inc_sweeps = None
        self.sweeps = None
        self.n_sweeps = None
        # Fitting parameters
        self._fitParams = None
        self._fitData = None #store the fitted data
        


    @property
    def t(self):
        '''
        return private attribute of time axis.
        Returns
        -------
        TYPE
            DESCRIPTION.
        '''
        return self._t

    @t.setter
    def t(self):
        '''
        Parameters
        ----------
        value : TYPE
            DESCRIPTION.
        Returns
        -------
        None.

        '''
        print('not allowed to change like this')

    def set_t0(self, val):
        '''setting t0 by given value
        If more datasets loaded, It changes
        t0 for idx's dataset
        author DP, last change 28/04/20'''
        if sup.is_num(val):
            self._t = self._t - val
            self.t0 += val
        else:
            raise ValueError('Value has to be numeric, not a string.')

    def rem_bg(self, val):
        ''' remove background, where the background is calculated as the
            time-averaged spectra of all points before 'tPos'
            author DP, last change 28/04/20'''
        if sup.is_num(val):
            idx = self._t < val
            if sum(idx) == 0:
                idx[0] = True
                print('Warning: all time points after tPos')
            bg = np.mean(self.data[idx, :], axis=0)
            self.data = self.data - bg*np.ones(self.data.shape)
        else:
            raise ValueError('Value has to be numeric, not a string.')

    def rem_region(self, wl_min, wl_max):
        '''set data to 0 for spectral region of 2D data
         - on the half-open interval [wl_min, wl_max)
        author DP, last change 28/04/20'''
        if sup.is_num(wl_min) and sup.is_num(wl_max):
            i_min, i_max = sup.get_idx(wl_min, wl_max, axis=self.wl)
            print(self.wl[i_min], self.wl[i_max], self.wl)
            self.data[:, i_min:i_max] = 0
        else:
            raise ValueError('Value has to be numeric, not a string.')

    @refresh_vals
    def cut_wl(self, wlmin, wlmax):
        '''select wl range between wlMin and wlMax
        - returns closed interval [wlmin, wlmax]
        author DP, last change 28/04/20'''
        if sup.is_num(wlmin) and sup.is_num(wlmax):
            imn, imx = sup.get_idx(wlmin, wlmax, axis=self.wl)
            self.wl = self.wl[imn:imx+1]
            self.data = self.data[:, imn:imx+1]
            try:
                self.sweeps = [self.sweeps[i][:, imn:imx+1]
                               for i in range(self.n_sweeps)]
            except:
                print('No sweeps')
            self.wlmax_id = imx + 1
            self.wlmin_id = imn
        else:
            raise ValueError('Value has to be numeric, not a string.')

    @refresh_vals
    def cut_t(self, tmin, tmax):
        '''removes timepoints between 'tMin' and 'tMax'
        author DP, last change 28/04/20'''
        if sup.is_num(tmin) and sup.is_num(tmax):
            imn, imx = sup.get_idx(tmin, tmax, axis=self._t)
            self._t = self._t[imn:imx+1]
            self.data = self.data[imn:imx+1, :]
            try:
                self.sweeps = [self.sweeps[i][imn:imx+1, :]
                               for i in range(self.n_sweeps)]
            except:
                print('No sweeps')
            self.tmax_id = imx + 1
            self.tmin_id = imn
        else:
            raise ValueError('Value has to be numeric, not a string.')

    def calc_spe(self, rng: list):
        '''
        calculates time-averaged spectra, with timepoints defined as:
        rng = [t1min, t1max, t2min, t2max, ... txmin, txmax]
        output is stored in obj.spe
        - wl range on closed interval [tmin, tmax]
        author DP, last change 28/04/20
        '''
        self.spe = []
        self.spe_rng = rng
        zipped_tuple = tuple(zip(rng[::2], rng[1::2]))

        for i in zipped_tuple:
            mean = sup.mean_subarray(self.data,
                                     axis=0,
                                     rng=i,
                                     ax_data=self._t)
            self.spe.append(mean)

    def calc_kin(self, rng):
        '''
        calculates time-averaged spectra, with timepoints defined as:
        rng = [wl1 min, wl1 max, wl2 min, wl2 max, ... wlx min, wlx max]
        the output is stored in self.kin, using the time axis
        self.t
        - mean returned on closed interval [wlmin, wlmax]
        author DP, last change 28/04/20
        TODO: recalculation should delete fitParams I think
        '''
        self.kin = []
        self.kin_rng = rng
        zipped_tuple = tuple(zip(rng[::2], rng[1::2]))

        for i in zipped_tuple:
            mean = sup.mean_subarray(self.data,
                                     axis=1,
                                     rng=i,
                                     ax_data=self.wl)
            self.kin.append(mean)

    @refresh_vals
    def new_average(self, include):
        '''include sweeps from binary list:
        include = [0,1,1,0...0,1]
        author DP, last change 28/04/20
        TODO: this should recalculate data (kin/spe/fits)'''
        if len(include) != self.n_sweeps:
            raise ValueError(f'list has to be lenght = {self.n_sweeps}')

        self.inc_sweeps = include
        newav = sum(self.sweeps[i]
                    for i in range(len(include))
                    if include[i] == 1)
        self.data = newav / sum(include)

    def recalc(self):
        '''
        Reculculates all generated data if they exist
        TODO: what if I need to pass more attributes to the method.
        Returns
        -------
        None.
        '''
        print('running recalc.')
        lookup_attr = (('kin', 'calc_kin', 'kin_rng'),
                       ('spe', 'calc_spe', 'spe_rng'),
                       ('fit_params', 'fit_kin', 'par_in'))
        for attr, method, to_pass in lookup_attr:
            if attr in self.__dict__ and self.__dict__[attr] is not None:
                print(f'Calling {Trs.__dict__[method]} because data changed')
                Trs.__dict__[method](self, self.__dict__[to_pass])

    def comp_sweep_kin(self, rng):
        '''compare kinetics from different sweeps within rng of WL
        rng = [wl1 min, wl1 max, wl2 min, wl2 max, ... wlx min, wlx max]
        author DP, last change 28/04/20'''
        idx = sup.get_idx(*rng, axis=self.wl)
        _, ax1 = plt.subplots()
        for j in range(self.n_sweeps):
            cmap = cm.gist_heat((j) / self.n_sweeps, 1)
            for i in range(int(len(rng)/2)):
                kin = np.mean(self.sweeps[j][:, idx[2*i]:idx[2*i+1]],
                              axis=1)
            if self.inc_sweeps[j]:
                ax1.plot(self._t, kin,
                         label=j,
                         color=cmap)
            else:
                ax1.plot(self._t, kin,
                         '--', linewidth=1,
                         label=f'{j} not in av',
                         color=cmap)
        # TODO works only for single rng.
        kin_av = np.mean(self.data[:, idx[2*i]:idx[2*i+1]],
                         axis=1)
        plt.plot(self._t, kin_av, linewidth=3, label='av kin')
        plt.xscale('Log')
        plt.legend()
        plt.show()

    @refresh_vals
    def invert_sweeps(self, invert):
        '''invert sweeps from binary list
        invert = [0,1,1,0...0,1]
        author DP, last change 09/06/20
        TODO: This calls decorator twice because of self.new_average'''
        if len(invert) != self.n_sweeps:
            raise ValueError('list has to be lenght = {self.n_sweeps}')

        for i, j in enumerate(invert):
            if j:
                self.sweeps[i] = -self.sweeps[i]
        # recalculating Average data
        self.new_average(self.inc_sweeps)

    @plot.title_plot
    @plot.log_xscale
    @plot.normalize_plot
    def plot_kin(self, **kwargs):
        fig_kin = plt.figure()
        for i, line in enumerate(self.kin):
            plt.plot(self._t, line, label=i)
        self.figure = fig_kin
        return fig_kin

    @plot.title_plot
    @plot.log_xscale
    @plot.normalize_plot
    def plot_spe(self, **kwargs):
        fig_spe = plt.figure()
        for i, line in enumerate(self.spe):
            plt.plot(self.wl, line, label=i)
        self.figure = fig_spe
        return fig_spe

    def fit_single_kin(self, nexp=1, rng=None, t_lims=None, **kwargs):
        gl_par = kwargs.get('glob', None)
        if rng is None:
            if self.kin is None:
                print('You have to specify range')
                return
        else:
            self.calc_kin(rng)
        data = self.kin
        t, data = ft.x_limits(self.t, data, t_lims)

        # for non-global fits (Dunno if it should be splitted into two methods)
        fit = []
        plt.figure()
        for i in range(len(data)):
            fit.append(ft.fit_kinetics(t[i], data[i], nexp,
                                       const=0))
            plt.plot(t[i], data[i], 'o')
            plt.plot(t[i], ft.exp_model(fit[-1].x, t[i],
                                        nexp), 'k-')
        plt.xscale('log')
        plt.show()

        # for GLOBAL fit of some params.
        if gl_par is not None:
            fit_glob = ft.fit_kinetics_global(t, data, gl_par, nexp)
            fit_result = ft.exp_model_gl(fit_glob.x,
                                         bool_gl=gl_par,
                                         x=t,
                                         n=nexp)
            for i in range(len(t)):
                plt.plot(t[i], data[i], 'o', label=i)
                plt.plot(t[i], fit_result[i], 'k-')
            plt.xscale('log')
            plt.legend()
            plt.show()
            return fit, fit_glob
        else:
            return fit

    def SVD(self, plot = 'y'):
        '''Function to perform single value decomposition on TA data, possible to plot spectral significant components, time series and sigma/s values
        author VG last editied 1/06/2020'''
        t = self._t[self._t>0] #predifine T larger than 0 for fitting
        DTT = self.data.T[:,self._t>0]  # scale DTT data accordingly
        wl = self.wl

        U, S, VT = np.linalg.svd(DTT,full_matrices=False) #SVD
        P = U * S**0.5 #Spectral signif. components
        T = S**0.5 * VT.T #Series signif. components
        

        if plot == 'y' or plot == 'yes':
            self._figure = plt.figure(figsize = [12,4.5])
            ax1 = self._figure.add_subplot(131)
            ax1.semilogy(S,'o') # Plot s/sigma values
            ax1.set_title('S-values')
            
            ax2 = self._figure.add_subplot(132)
            ax2.plot(wl,P) # plot spectral significant components
            ax2.set_title('Spectral Significant Components P\n ($P = U * \sqrt{S}$)')
            
            ax3 = self._figure.add_subplot(133)
            ax3.plot(T) #plot time series significant componentd
            ax3.set_title('Timeseries of Significant Components T\n ($T = \sqrt{S}*V\'$)')

    def SVDfit(self,components = 2,function=None,k0=[],pos=[],C0=[]):
        '''Fiting procedure using SVD extracted singificant components, to be implemented. Author VG, last edited 24/6/2020'''
        # TODO, Use functions in fitting.py for error optimization
        # and define a func(x,p,nexp,d1=[],d2=[]) as intrinsic function if no external function is supplied
        ### Inplement a function to check what time units are used, and make sure time is in seconds
        #timeconversion = 1e-9 #
        t = self._t[self._t>0]*self.t_conversion #predifine T larger than 0 for fitting
        DTT = self.data.T[:,self._t>0]  # scale DTT data accordingly
        wl = self.wl
        self.checkFitParams()

        U, S, VT = np.linalg.svd(DTT,full_matrices=False) #SVD
        P = U * S**0.5 #Spectral signif. components
        T = S**0.5 * VT.T #Series signif. components
        PP = P[:,:components] 
        TT = T[:,:components]

        if function == None:
            nexp = components #Set standard exponetial decay with n components the same as spectral components
            print('Not implemented yet - please supply function')
        else:
            k = k0;
            var = k[pos]
            self._fit = optim.minimize(ft.rotation,var,args=(k,pos,TT,PP,DTT,C0,t,function),method='nelder-mead',options={'xatol': 1e-6, 'disp': True, 'maxiter':1000})
            self._fitParams.append(self._fit.x)
            ### ideally this can be obtained directly from ft.rotation() or rotation function is moved here and global variables is used...
            k = self._fit.x
            C = odeint(function,C0,t,args=(k,)) #calculate concentration from model
            R = T.T @ np.linalg.pinv(C.T) #calculat rotation matrix
            V = P @ R; # calculate spectral components
            calc = V @ C.T #calculate 2D map
            res = (DTT-calc) #calculate residual
            ###

            self._fitData.append(calc) #store the fitted data
            self._spectralComponents = V
            self._figure = plt.figure(figsize = [12,10])
            I = np.linalg.pinv(self._spectralComponents)@DTT #Extract spectral dynamics from experimental DTT
            self._fitData.append(I)  # Add spectral dynamics
            self._fitData.append(C)     #Add calculated dynamics from fit
            residual = DTT-calc

            #Plotting results
            ## To add, use plotting decorators to introduce handles
            ax1 = self._figure.add_subplot(331)
            ax1.contourf(wl,t,DTT.T)
            ax1.set_title('$\Delta T/T$')
            ax1.set_yscale('log')
            ax1.set_ylabel('Time (s)')
            ax1.set_xlabel('Wavelength (nm)')

            ax2 = self._figure.add_subplot(332)
            ax2.plot(wl,P) # plot spectral significant components
            ax2.set_title('Spectral Significant Components P\n ($P = U * \sqrt{S}$)')
            ax2.set_ylabel('A.U.')
            ax2.set_xlabel('Wavelength (nm)')

            ax3 = self._figure.add_subplot(333)
            ax3.plot(T) #plot time series significant componentd
            ax3.set_title('Timeseries of Significant Components T\n ($T = \sqrt{S}*V\'$)')
            ax3.set_xlabel('Time (s)')
            ax3.set_ylabel('A.U.')

            ax4 = self._figure.add_subplot(334)
            ax4.contourf(wl,t,calc.T)
            ax4.set_title('$Fit Result$')
            ax4.set_yscale('log')
            ax4.set_ylabel('Time (s)')
            ax4.set_xlabel('Wavelength (nm)')

            ax5 = self._figure.add_subplot(335)
            ax5.plot(wl,self._spectralComponents)
            ax5.set_title('$Spectra$')
            ax5.set_ylabel('$\Delta T/T$')
            ax5.set_xlabel('Wavelength (nm)')

            ax6 = self._figure.add_subplot(336)
            ax6.semilogx(t,C,'-r',label = 'Fit')
            ax6.semilogx(t,I.T,'o', label = 'experimental')
            ax6.set_title('$Population Dynamics$')
            ax6.set_ylabel('Time (s)')
            ax6.set_xlabel('Wavelength (nm)')
            ax6.legend()

            ax7 = self._figure.add_subplot(337)
            ax7.contourf(wl,t,residual.T)
            ax7.set_title('Residual$')
            #ax7.set_yscale('log')
            ax7.set_ylabel('Time (s)')
            ax7.set_xlabel('Wavelength (nm)')

            self._figure.tight_layout()

    # def reset_def_vals(self):
    #     '''
    #     sets all values to initial default state after loading.
    #     '''
    #     return

    # def exp_fit(self, kin, tlim):
    #     '''
    #     Fitting of kinetics

    #     Returns
    #     -------
    #     None.
    #     '''
    #     return
    def checkFitParams(self): ### Should be moved to fitting.py but I didn't get it to work with self referencing... VG 2020-06-24
        if self._fitParams is None:
            self._fitParams = []
            self._fitData = []
        else:
            a=input('Rewrite old fits [y/n]?')
            if a=='y':
                self._fitParams = []
                self._fitData = []
            else:
                print('I will append fit parametres to existing field')
