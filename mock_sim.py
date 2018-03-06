import astropy.table as atpy
import read_girardi
import numpy as np
import scipy.spatial
import astropy.units as auni
import stream_num_cal as snc
import simple_stream_model as sss 
import matplotlib.pyplot as plt


betw  = lambda x,x1,x2:(x>=x1)&(x<=x2)

def getMagErr(mag, filt, survey='LSST'):
    if survey == 'LSST':
        import photErrorModel as pem
        lem = pem.LSSTErrorModel()
        #minmagerr = 0.01
        magerr = lem.getMagError(mag,'LSST_'+filt)
        return magerr

def getMagErrVec(mag, filt, survey='LSST'):
    maggrid = np.linspace(15,28,1000)
    res = [getMagErr(m,filt,survey) for m in maggrid]
    res=scipy.interpolate.UnivariateSpline(maggrid,res,s=0)(mag)
    return res


def getMagLimit(filt, survey='LSST'):
    return 27

def getIsoCurve(iso):
    mini = iso['M_ini']
    g=iso['DES-g']
    r=iso['DES-r']
    magstep = 0.01
    res_g, res_r = [],[]
    for i in range(len(mini)-1):
        l_g,l_r = g[i],r[i]
        r_g,r_r = g[i+1],r[i+1]
        npt = max(abs(r_g-l_g),abs(r_r-l_r))/magstep+2
        ggrid = np.linspace(l_g,r_g,npt)
        rgrid = np.linspace(l_r,r_r,npt)
        res_g.append(ggrid)
        res_r.append(rgrid)
    res_g, res_r = [np.concatenate(_) for _ in [res_g, res_r]]
    return res_g, res_r

    
def get_mock_density(distance, isoname, survey,
                         mockfile='stream_gap_mock.fits', mockarea=100):
    """
    Distance in kpc,
    isochrone name
    survey
    """
    minerr = 0.01
    dm = 5*np.log10(distance*1e3)-5
    iso = read_girardi.read_girardi(isoname)
    xind = iso['stage']<=3
    r_mag_limit = getMagLimit('r',survey)
    gcurve, rcurve = getIsoCurve(iso)
    gcurve,rcurve = [ _+ dm  for _ in [gcurve,rcurve]]
    mincol,maxcol=-0.3,1.2
    minmag,maxmag=15,28
    colbin=0.01
    magbin=0.01
    grgrid,rgrid = np.mgrid[mincol:maxcol:colbin,minmag:maxmag:magbin]
    colbins = np.arange(mincol,maxcol,colbin)
    magbins = np.arange(minmag,maxmag,magbin)
    ggrid = grgrid+rgrid
    arr0 = np.array([(ggrid).flatten(),rgrid.flatten()]).T
    arr = np.array([gcurve,rcurve]).T
    tree = scipy.spatial.KDTree(arr)
    D,xind=tree.query(arr0)
    gerr = getMagErrVec(ggrid.flatten(), 'g', survey).reshape(ggrid.shape)
    rerr = getMagErrVec(rgrid.flatten(), 'r', survey).reshape(rgrid.shape)
    gerr,rerr = [np.maximum(_,minerr) for _ in [gerr,rerr]]
    dg = ggrid-gcurve[xind].reshape(ggrid.shape)
    dr = rgrid-rcurve[xind].reshape(rgrid.shape)
    
    thresh = 2 # 2 sigma
    
    mask = (np.abs(dg/gerr)<2)&(np.abs(dr/rerr)<2)
    dat = atpy.Table().read(mockfile)
    g, r = dat['g'], dat['r']
    colid = np.digitize(g-r,colbins)-1
    magid = np.digitize(r,magbins)-1
    xind = betw(colid,0,grgrid.shape[0]-1)&betw(magid,0,grgrid.shape[1])& (
        r<r_mag_limit)
    return xind.sum()/mockarea


def predict_gap_depths(mu, distance_kpc, survey, width_pc):
    """Arguments:
    mu -- surfgace brightness  mag/sq.arcsec^2
    distance_kpc -- distance in kpc
    survey -- strign
    width_pc -- width of the stream in pc)
    Returns:
    the array of halo masses
    the array of theoretically predicted gap depths
    the array of potentially observable gap depths
    """
    width_deg = np.rad2deg(width_pc/distance_kpc/1e3)
    mgrid = 10**np.linspace(5.5,8.5,10)
    gap_depths = np.array([sss.gap_depth(_) for _ in mgrid])
    gap_sizes_deg = np.array([sss.gap_size(_,dist=distance_kpc*auni.kpc)/auni.deg for _ in mgrid])
    #gap_sizes_deg = np.rad2deg(gap_size/ distance/1e3)
    isoname = 'iso_a12.0_z0.00020.dat'
    maglim = getMagLimit('r', survey)
    dens_stream = snc.nstar_cal(mu, distance_kpc, maglim, frac = 0.6)
    dens_bg = get_mock_density(distance_kpc, isoname, survey,
                         mockfile='stream_gap_mock.fits', mockarea=100)
    print (dens_bg,dens_stream)
    N = len(gap_sizes_deg)
    detfracs  = np.zeros(N)
    for i in range(N):
        nbg = dens_bg * width_deg * gap_sizes_deg[i]*2
        nstr = dens_stream * width_deg * gap_sizes_deg[i]*2
        print ('Nstream', nstr,'Nbg', nbg)
        detfrac = 3*np.sqrt(nbg+nstr)/nstr
        detfracs[i]=detfrac
    return (mgrid, gap_depths,detfracs)
    #plt.plot(mgrid, detfracs)
