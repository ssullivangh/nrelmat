# Copyright 2013 National Renewable Energy Laboratory, Golden CO, USA
# This file is part of NREL MatDB.
#
# NREL MatDB is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# NREL MatDB is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with NREL MatDB.  If not, see <http://www.gnu.org/licenses/>.

import gzip   # preload gzip since tarfile loads it dynamically
import json, os, re, StringIO, sys, tarfile, traceback
import psycopg2
from pyramid.view import view_config
from pyramid.view import forbidden_view_config
from pyramid.httpexceptions import HTTPFound
from pyramid.httpexceptions import HTTPNotFound

import pyramid.security as security
import pyramid.renderers as renderers
import pyramid.response
import pyramid.url
import authSpec
import xyzToSmol

from ColumnDesc import ColumnDesc

#====================================================================

# xxxxxxxxxxxxxxxxxxx to do xxxxxxxxxxxxxxxxx
# 
# Three auth methods:
#   authSecurity
#   authSession
#   authHtml: new random each time
# 
# doc all.
# 
# read docs on traversal:
# http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/muchadoabouttraversal.html
# http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/hellotraversal.html
# http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/traversal.html

# all xxx, ##
# merge up
# xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


#====================================================================

# xxx del
elementsLower = [
  'h',  'he', 'li', 'be', 'b',  'c',  'n',  'o',  'f',  'ne',
  'na', 'mg', 'al', 'si', 'p',  's',  'cl', 'ar', 'k',  'ca',
  'sc', 'ti', 'v',  'cr', 'mn', 'fe', 'co', 'ni', 'cu', 'zn',
  'ga', 'ge', 'as', 'se', 'br', 'kr', 'rb', 'sr', 'y',  'zr',
  'nb', 'mo', 'tc', 'ru', 'rh', 'pd', 'ag', 'cd', 'in', 'sn',
  'sb', 'te', 'i',  'xe', 'cs', 'ba', 'la', 'ce', 'pr', 'nd',
  'pm', 'sm', 'eu', 'gd', 'tb', 'dy', 'ho', 'er', 'tm', 'yb',
  'lu', 'hf', 'ta', 'w',  're', 'os', 'ir', 'pt', 'au', 'hg',
  'tl', 'pb', 'bi', 'po', 'at', 'rn', 'fr', 'ra', 'ac', 'th',
  'pa', 'u',  'np', 'pu', 'am', 'cm', 'bk', 'cf', 'es', 'fm',
  'md', 'no', 'lr', 'rf', 'db', 'sg', 'bh', 'hs', 'mt', 'ds',
  'rg', 'cn', 'uut', 'fl', 'uup', 'lv', 'uus', 'uuo']

#====================================================================

elementsStandard = [
  'H',  'He', 'Li', 'Be', 'B',  'C',  'N',  'O',  'F',  'Ne',
  'Na', 'Mg', 'Al', 'Si', 'P',  'S',  'Cl', 'Ar', 'K',  'Ca',
  'Sc', 'Ti', 'V',  'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
  'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr', 'Y',  'Zr',
  'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
  'Sb', 'Te', 'I',  'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd',
  'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb',
  'Lu', 'Hf', 'Ta', 'W',  'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg',
  'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn', 'Fr', 'Ra', 'Ac', 'Th',
  'Pa', 'U',  'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm',
  'Md', 'No', 'Lr', 'Rf', 'Db', 'Sg', 'Bh', 'Hs', 'Mt', 'Ds',
  'Rg', 'Cn', 'Uut', 'Fl', 'Uup', 'Lv', 'Uus', 'Uuo']


#====================================================================


def getModelColDescs():

  columnDescs = [

    # The dbName must be lower case since the Postgresql
    # DB API descriptor returns all lower case values.

    #           dbName       tag       fmt   desc
    ColumnDesc('mident',    'id',      '%d', 'MatDB ID'),
    ColumnDesc('wrapid',    'wrapId',  '%s', 'Identifier for this upload'),
    ColumnDesc('abspath',   'absPath', '%s', 'absolute file path'),
    ColumnDesc('relpath',   'relPath', '%s', 'relative file path'),
    ColumnDesc('icsdnum',   'icsdNum', '%d', 'ICSD id'),

    ColumnDesc('magtype',   'magType', '%s',
      'mag moment type: hsf=hs-ferro, hsaf=hs-antiferro, nm=non-mag'),
    ColumnDesc('magnum',   'magNum',   '%d',
      'mag moment num for hs, ls antiferro'),

    ColumnDesc('relaxtype',   'relaxType', '%s',
      'Type of run: std=standard, rc=relax_cellshape, ri=relax_ions'),

    ColumnDesc('relaxnum',   'relaxNum', '%d',
      'Folder num for rc or ri'),
    ColumnDesc('excmsg',   'excMsg', '%s',
      'exception msg from digestVasp.py'),
    ColumnDesc('exctrace', 'excTrace', '%s',
      'exception trace from digestVasp.py'),

    #--- program, version, date etc ---
    ColumnDesc('rundate', 'runDate', '%s', 'run date'),
    ColumnDesc('itertotaltime', 'runTime', '%0.2f', 'run time in seconds'),

    #--- incar parameters ---
    ColumnDesc('systemname', 'systemName', '%s', 'system name'),
    ColumnDesc('encut_ev', 'encut', '%g', 'INCAR encut parameter, eV'),
    ColumnDesc('ibrion', 'ibrion', '%d', 'INCAR ibrion parameter'),
    ColumnDesc('isif', 'isif', '%d', 'INCAR isif parameter'),

    #--- kpoints ---
    #--- general parameters ---
    #--- atom info ---
    ColumnDesc('numatom', 'numAtom', '%d', 'num atoms in unit cell'),
    ColumnDesc('typenames', 'typeNames', '[%s]', 'atom types'),
    ColumnDesc('typenums', 'typeNums', '[%d]', 'num of each type of atom'),
    ColumnDesc('typemasses', 'typeMasses', '[%g]',
      'atom mass for each type'),
    ColumnDesc('typepseudos', 'typePseudos', '[%s]',
      'atom pseudopotential name for each type'),
    ColumnDesc('typevalences', 'typeValences', '[%d]',
      'atom valences for each type'),

    ColumnDesc('atomnames', 'atomNames', '[%s]', 'atom names'),
    ColumnDesc('atommasses_amu', 'atomMasses_amu', '[%g]', 'atom masses'),
    ColumnDesc('atompseudos', 'atomPseudos', '[%s]',
      'atom pseudopotential names'),
    ColumnDesc('atomvalences', 'atomValences', '[%d]',
      'atom valences in cell'),

    #--- initial structure ---
    ColumnDesc('initialbasismat', 'initialBasisMat', '[[%g]]',
      'initial basis matrix'),
    ColumnDesc('initialrecipbasismat', 'initialRecipBasisMat', '[[%g]]',
      'initial reciprocal basis matrix'),
    ColumnDesc('initialcartesianposmat', 'initialCartesianPosMat', '[[%g]]',
      'initial cartesian position matrix'),
    ColumnDesc('initialdirectposmat', 'initialDirectPosMat', '[[%g]]',
      'initial direct position matrix'),

    #--- final structure ---
    ColumnDesc('finalbasismat', 'finalBasisMat', '[[%g]]',
      'final basis matrix (rows)'),
    ColumnDesc('finalrecipbasismat', 'finalRecipBasisMat', '[[%g]]',
      'final reciprocal basis matrix (rows)'),
    ColumnDesc('finalcartesianposmat', 'finalCartesianPosMat', '[[%g]]',
      'final cartesian position matrix (row per atom, = direct * basis)'),
    ColumnDesc('finaldirectposmat', 'finalDirectPosMat', '[[%g]]',
      'final direct position matrix (row per atom, = cartesian * recipBasis)'),

    #--- final volume and density ---
    ColumnDesc('finalvolumevasp_ang3', 'finalVolume', '%.4f',
      'final cell volume, Angstrom3'),
    ColumnDesc('density_g_cm3', 'density', '%.4f',
      'final cell density, g/cm3'),

    #--- last calc forces ---
    ColumnDesc('finalforcemat_ev_ang', 'finalForceMat', '[[%g]]',
      'final force matrix, eV/Ang, row per atom'),
    ColumnDesc('finalstressmat_kbar', 'finalStressMat', '[[%g]]',
      'final stress matrix, kbar, (3x3)'),
    ColumnDesc('finalpressure_kbar', 'finalPressure', '%g',
      'final pressure, Kbar'),

    #--- eigenvalues and occupancies ---
    ColumnDesc('eigenmat', 'eigenMat', '[[%g]]',
      'final eigenvalue matrix ([spin][kpoint][band])'),

    #--- energy, efermi0 ---
    ColumnDesc('energynoentrp', 'finalEnergyWoEntropy', '%.2f',
      'final total energy without entropy'),
    ColumnDesc('energyperatom', 'energyPerAtom', '%.2f',
      'final total energy without entropy, per atom in cell'),
    ColumnDesc('efermi0', 'efermi0', '%.2f',
      'fermi energy at 0K'),

    #--- cbMin, vbMax, bandgap ---
    ColumnDesc('cbmin', 'cbMin', '%.3f',
      'conduction band minimum energy'),
    ColumnDesc('vbmax', 'vbMax', '%.3f',
      'valence band maximum energy'),
    ColumnDesc('bandgap', 'bandgap', '%.3f',
      'bandgap'),

    #--- augmented items ---
    ColumnDesc('formula', 'formula', '%s',
      'chemical formula'),
    ColumnDesc('chemtext', 'chemText', '%s',
      'chemical formula with spaces'),
    ColumnDesc('minenergyid', 'minEnergyID', '%d',
      'id having min energy for this formula'),
    ColumnDesc('enthalpy', 'enthalpy', '%.2f',
      'final enthalpy, eV/atom'),

    #--- metadata ---
    ColumnDesc('hashstring', 'hash', '%s',
      'sha512 sum of vasprun.xml file'),
    ColumnDesc('meta_parents', 'parents', '[%s]',
      'sha512 sums of parent vasprun.xml files'),
    ColumnDesc('meta_firstname', 'firstName', '%s',
      'First name of the researcher.'),
    ColumnDesc('meta_lastname', 'lastName', '%s',
      'Last name of the researcher.'),
    ColumnDesc('meta_publications', 'publications', '[%s]',
      'DOIs of publications'),
    ColumnDesc('meta_standards', 'standards', '[%s]',
      'computational standards'),
    ColumnDesc('meta_keywords', 'keywords', '[%s]',
      'keywords to aid searching'),
    ColumnDesc('meta_notes', 'notes', '%s',
      'notes'),
  ]

  return columnDescs


#====================================================================


def getContribColDescs():

  columnDescs = [

    # The dbName must be lower case since the Postgresql
    # DB API descriptor returns all lower case values.

    #           dbName        tag        fmt    desc
    ColumnDesc('wrapid',     'wrapId',   '%s',  'Identifier for this upload'),
    ColumnDesc('curdate',    'date',     '%s',  'Date of upload'),
    ColumnDesc('userid',     'userId',   '%s',  'userId'),
    ColumnDesc('hostname',   'hostName', '%s',  'hostname'),
    ColumnDesc('topdir',     'topDir',   '%s',  'top dir'),
    ColumnDesc('numkeptdir',  'numKeptDir', '%d', 'num subdirs uploaded'),
    ColumnDesc('reldirs',    'relDirs',  '[%s]', 'relative upload subdirs'),
  ]

  return columnDescs

#====================================================================

def getIcsdColDescs():

  columnDescs = [

    # The dbName must be lower case since the Postgresql
    # DB API descriptor returns all lower case values.

    #           dbName         tag             fmt   desc
    ColumnDesc('cident',       'id',           '%d', 'MatDB CID'),
    ColumnDesc('chemname',     'chemName',     '%s', 'Chemical name'),
    ColumnDesc('mineralname',  'mineralName',  '%s', 'Mineral name'),
    ColumnDesc('symgroupname', 'symGroupName', '%s', 'Symmetry group name'),
    ColumnDesc('symgroupnum',  'symGroupNum',  '%d', 'Symmetry group num'),
  ]

  return columnDescs

#====================================================================




# Return the elements for the navigation area
# at the upper left.
# Used by templates/tmBase.py.

def getNavList( request):
  authedSecure  = security.authenticated_userid( request)
  navList = [
    [ 'Home', request.route_url('rtHome')]]

  if authedSecure:
    navList.append(
      [ 'Query', request.route_url('rtQueryStd', queryRest='')])
    ##navList.append(
    ##  [ 'Advanced Query', request.route_url('rtQueryAdv', queryRest='')])
    navList.append(
      [ 'Contributions', request.route_url('rtContrib', queryRest='')])
    navList.append(
      [ 'Logout', request.route_url('rtLogout')])

  else:
    navList.append(
      [ 'Login', request.route_url('rtLogin')])

  return navList


#====================================================================


@forbidden_view_config( renderer='tmLogin.mak')


#====================================================================

# Login

@view_config( route_name='rtLogin', renderer='tmLogin.mak')

def vwLogin(request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  logIt('vwLogin', request)
  if buglev >= 5:
    print '\nvwLogin: request:\n%s' % (request,)
    print '\nvwLogin: request.params: %s' % (request.params,)
    print '\nvwLogin: auth_userid: %s' \
      % (security.authenticated_userid( request),)
    print '\nvwLogin: request.session: %s' % (request.session,)

  errMsg = 'Please login'
  userid = ''
  password = ''
  if 'submitTag' in request.params:
    userid = request.params['userid']
    password = request.params['password']
    if buglev >= 5:
      print 'vwLogin: form userid: %s' % ( repr(userid),)
    if authSpec.authCheckUseridPassword( userid, password):
      if buglev >= 5: print 'vwLogin: *** form userid is ok ***'
      headers = security.remember(request, userid)
      request.session['authedSession'] = userid
      if buglev >= 5:
        print 'vwLogin: ok: auth_userid: %s' \
          % (security.authenticated_userid( request),)

      # *** Redirect ***
      return HTTPFound(
        location = request.route_url('rtHome'), headers = headers)

    errMsg = 'Incorrect userid or password'
    if buglev >= 5: print 'vwLogin: *** form userid is incorrect ***'

  if buglev >= 5:
    print 'vwLogin: *** need password ***'
    print 'vwLogin: ok: auth_userid: %s' \
      % (security.authenticated_userid( request),)
  return dict(
    errMsg        = errMsg,
    url           = request.application_url,
    userid        = userid,
    password      = password,
    authedSecure  = security.authenticated_userid( request),
    authedSession = request.session.has_key('authedSession'),
    navList       = getNavList( request),
  )


#====================================================================

# Logout

@view_config(route_name='rtLogout')

def vwLogout(request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  logIt('vwLogout', request)
  if buglev >= 5: print 'vwLogout: auth_userid: %s' \
      % (security.authenticated_userid( request),)
  headers = security.forget(request)
  if request.session.has_key('authedSession'):
    del request.session['authedSession']
  # *** Redirect ***
  return HTTPFound(
    location = request.route_url('rtHome'), headers = headers)



#====================================================================

# Home

@view_config(route_name='rtHome', renderer='tmHome.mak')

def vwHome(request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  logIt('vwHome', request)
  if buglev >= 5: print 'vwHome: auth_userid: %s' \
      % (security.authenticated_userid( request),)
  errMsg = ''
  return dict(
    errMsg        = errMsg,
    authedSecure  = security.authenticated_userid( request),
    authedSession = request.session.has_key('authedSession'),
    navList    = getNavList( request),
  )


#====================================================================

# Not found.
# Render the template directly and return 404.

def vwNotFound(request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  logIt('vwNotFound', request)
  if buglev >= 5: print 'vwNotFound: auth_userid: %s' \
      % (security.authenticated_userid( request),)
  errMsg = 'Page not found'
  dct = dict(
    errMsg        = errMsg,
    authedSecure  = security.authenticated_userid( request),
    authedSession = request.session.has_key('authedSession'),
    navList    = getNavList( request),
  )
  resp = renderers.render_to_response('tmNotFound.mak', dct, request=request)
  resp.status = '404 Not Found'
  return resp


# xxx file timestamp
# folder name, not file name?



#====================================================================

# QueryStd

@view_config(route_name='rtQueryStd', renderer='tmQueryStd.mak',
  permission='permEdit')

def vwQueryStd( request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  logIt('vwQueryStd', request)

  queryFieldStg = settings['db_query_fields']
  queryFields = queryFieldStg.split()
  showFields = [nm.strip('*') for nm in queryFields if nm.endswith('*')]
  queryFields = map( lambda x: x.strip('*'), queryFields)

  if buglev >= 5:
    print 'vwQueryStd: auth_userid: %s' \
      % (security.authenticated_userid( request),)
    print 'vwQueryStd: route: %s' \
      % (request.route_url('rtQueryStd', queryRest='someRest'),)
    print 'vwQueryStd: path: %s' \
      % (request.route_path('rtQueryStd', queryRest='someRest'),)
    print 'vwQueryStd: current_route_url: %s' \
      % (request.current_route_url( queryRest='someRest'),)
    print 'vwQueryStd: current_route_path: %s' \
      % (request.current_route_path( queryRest='someRest'),)
    print 'vwQueryStd: matchdict: %s' % (request.matchdict,)
    print 'vwQueryStd: matched_route: %s' % (request.matched_route,)
    print 'vwQueryStd: GET: %s' % (request.GET,)
    print 'vwQueryStd: POST: %s' % (request.POST,)

  dlmap = request.GET.dict_of_lists()
  if buglev >= 5:
    print 'vwQueryStd: dlmap:'
    keys = dlmap.keys()
    keys.sort()
    for key in keys:
      print '  dlmap key: %s  value: %s' % (repr(key), repr(dlmap[key]),)
    print ''

  columnDescs = getModelColDescs()
  descMap = getDescMap( 'model.', columnDescs)    # dbColName -> ColumnDesc

  columnDescs = getIcsdColDescs()
  descMap.update( getDescMap( 'icsd.', columnDescs))

  varMap = {
    # userName    dbName
    # --------    ----------
    'bandgap'   : 'model.bandgap',
    'energy'    : 'model.energyperatom',
    'pressure'  : 'model.finalpressure_kbar',
  }

  varMapHtml = ''
  keys = varMap.keys()
  keys.sort()
  for key in keys:
    dbName = varMap[key]
    varMapHtml += (
        '    <tr>\n'
      + '      <th class="varMapRight"> %s </th>\n'
      + '      <td class="varMapLeft"> %s </td> </tr>\n' \
      + '    <tr>\n') % (key, descMap[dbName].desc,)

  pageStart = 0
  pageSize = 50

  db_rows = []
  errMsg = ''
  numTotal = 0
  pageNames = []
  currentPage = 0
  qlimit = 100
  qoffset = 0
  tableHtml = ''

  eleSyms = []
  if dlmap.has_key('qrequires'):         # if user pressed submit
    try:
      qset = dlmap['qset'][0].strip()
      qrequiresStg = dlmap['qrequires'][0].strip()
      qforbidsStg = dlmap['qforbids'][0].strip()
      qexpr = dlmap['qexpr'][0].strip()
      if dlmap.has_key('showLastNameStevanovic'):
        showLastNameStevanovic = True
      else: showLastNameStevanovic = False
      if dlmap.has_key('showLastNameZawadzki'):
        showLastNameZawadzki = True
      else: showLastNameZawadzki = False
      if dlmap.has_key('showMinEnergyOnly'):
        showMinEnergyOnly = True
      else: showMinEnergyOnly = False

      qrequirePairs = parseElements( qrequiresStg)
      qforbidPairs = parseElements( qforbidsStg)
      qrequireNames = [pair[0] for pair in qrequirePairs]
      qforbidNames = [pair[0] for pair in qforbidPairs]

      # Set currentPage, qoffset from submitStg
      submitStgs = dlmap['submitQuery']
      submitStg = submitStgs[0].strip()
      if re.match('^\d+', submitStg):
        currentPage = int( submitStg) - 1            # origin 0
        qoffset = currentPage * qlimit

      if buglev >= 1:
        print 'vwQueryStd: queryFields: %s' % (queryFields,)
        print 'vwQueryStd: showFields: %s' % (showFields,)
        print 'vwQueryStd: qset: %s' % (qset,)
        print 'vwQueryStd: qrequirePairs: %s' % (qrequirePairs,)
        print 'vwQueryStd: qforbidPairs: %s' % (qforbidPairs,)
        print 'vwQueryStd: qexpr: %s' % (qexpr,)
        print 'vwQueryStd: showLastNameStevanovic: %s' % (showLastNameStevanovic,)
        print 'vwQueryStd: showLastNameZawadzki: %s' % (showLastNameZawadzki,)
        print 'vwQueryStd: showMinEnergyOnly: %s' % (showMinEnergyOnly,)
        print 'vwQueryStd: currentPage: %d' % (currentPage,)
        print 'vwQueryStd: qoffset: %d' % (qoffset,)
        print 'vwQueryStd: qlimit: %d' % (qlimit,)

      whereClause = 'TRUE'

      if showLastNameStevanovic and showLastNameZawadzki: pass
      elif showLastNameStevanovic:
        whereClause += ' AND model.meta_lastname = \'Stevanovic\''
      elif showLastNameZawadzki:
        whereClause += ' AND model.meta_lastname = \'Zawadzki\''
      else: whereClause += ' AND FALSE'      # no results

      if showMinEnergyOnly:
        whereClause += ' AND model.mident = model.minenergyid'

      if len(qrequireNames) > 0:
        # Get list of names with single quotes, like ["'Mg'", "'Si'"]
        names = ['\'%s\'' % (nm,) for nm in qrequireNames]
        stg = ','.join( names)
        arStg = ' ARRAY[%s]' % (stg,)
        if qset == 'subset':
          whereClause += ' AND typeNames <@ %s' % (arStg,)
        elif qset == 'exact':
          whereClause += ' AND %s <@ typeNames AND typeNames <@ %s' \
            % (arStg, arStg,)
        elif qset == 'superset':
          whereClause += ' AND typeNames @> %s' % (arStg,)
        elif qset == 'formula':
          # Coordinate formula format with augmentDb.py: addChemforms
          formula = ''
          for pair in qrequirePairs:
            if len(formula) > 0: formula += ' '
            formula += pair[0]
            if pair[1] != 1:
              formula += str(pair[1])
          whereClause += ' AND formula = \'%s\'' % (formula,)

        else: errMsg += 'invalid qset: %s<br>\n' % (qset,)

      if len(qforbidNames) > 0:
        # Get list of names with single quotes, like ["'Mg'", "'Si'"]
        names = ['\'%s\'' % (nm,) for nm in qforbidNames]
        stg = ','.join( names)
        arStg = ' ARRAY[%s]' % (stg,)
        whereClause += ' AND (NOT typeNames && %s)' % (arStg,)

      if qexpr != '':
        toks = tokenize( varMap, qexpr)
        whereClause += ' AND ( %s )' % (' '.join( toks),)

      #qsort = dlmap['qsort'][0].strip()
      #sortFields = qsort.split()
      #for ii in range(len(sortFields)):   # translate tag to dbName
      #  nm = sortFields[ii]
      #  cdesc = None
      #  for cd in columnDescs:
      #    if cd.tag == nm:
      #      cdesc = cd
      #      break
      #  if cdesc == None:
      #    errMsg += 'unknown sort fields: "%s"<br>\n' % (nm,)
      #  sortFields[ii] = cdesc.dbName
      #sortFields.append('mident')               # always sort on mident last
      #sortStg = ', '.join( sortFields)

      sortStg = 'model.formula, icsd.symGroupNum'

      if buglev >= 1:
        #print 'vwQueryStd: sortFields: %s' % (sortFields,)
        print 'vwQueryStd: sortStg: %s' % (sortStg,)

      nameStg = ', '.join( queryFields)

      if buglev >= 1:
        print 'vwQueryStd: queryFields: %s' % (queryFields,)
        print 'vwQueryStd: showFields: %s' % (showFields,)
        print 'vwQueryStd: qoffset: %d' % (qoffset,)
        print 'vwQueryStd: qlimit: %d' % (qlimit,)

      query0 = 'set search_path to %s' % (settings['db_schema'],)

      fromClause = \
        'model LEFT OUTER JOIN icsd ON (model.icsdnum = icsd.icsdnum)'

      query1 = 'SELECT count(*) FROM %s WHERE %s' % (fromClause, whereClause,)

      query2 = 'SELECT %s FROM %s WHERE %s ORDER BY %s LIMIT %s OFFSET %s' \
        % (nameStg, fromClause, whereClause, sortStg, qlimit, qoffset,)

      queries = [query0, query1, query2]
      dbRes = dbQuery( buglev, settings, queries)
      if type(dbRes).__name__ == 'str':
        print '\nvwQueryStd: dbRes: %s' % (repr(dbRes),)
        errMsg += '%s<br>\n' % (dbRes,)
        numTotal = 0
      else:
        (msgs, colVecs, rowVecs) = dbRes
        numTotal = int( rowVecs[1][0][0])   # query 1, row 0, element 0
        db_rows = rowVecs[2]                # query 2
        for ii in range( 0, numTotal, qlimit):
          pageNames.append('%d' % (ii / qlimit + 1,))
        # Get icolMap: dbColName -> icol in queryFields
        icolMap = getIcolMap( descMap, queryFields)

        tableHtml = formatTableHtml(
          descMap, icolMap, showFields, colVecs, db_rows)
    except Exception, exc:
      traceback.print_exc( None, sys.stdout)
      errMsg = str( exc)

  else:
    qrequiresStg = 'Sn Zn'
    qset = 'superset'
    qforbidsStg = 'H'
    qexpr = '0 < bandgap and bandgap < 1.5'
    showLastNameStevanovic = True
    showLastNameZawadzki = True
    showMinEnergyOnly = True

    # qsort = 'energyPerAtom bandgap icsdNum dbId'

  ##if buglev >= 5: print 'vwQueryStd: db_rows: %s' % (db_rows,)

  qsetSubset = ''
  qsetExact = ''
  qsetSuperset = ''
  qsetFormula = ''
  if qset == 'subset': qsetSubset = 'checked="true"'
  if qset == 'exact': qsetExact = 'checked="true"'
  if qset == 'superset': qsetSuperset = 'checked="true"'
  if qset == 'formula': qsetFormula = 'checked="true"'

  return dict(
    qsetSubset     = qsetSubset,
    qsetExact      = qsetExact,
    qsetSuperset   = qsetSuperset,
    qsetFormula    = qsetFormula,
    qrequires      = qrequiresStg,
    qforbids       = qforbidsStg,
    qexpr          = qexpr,
    showLastNameStevanovic = showLastNameStevanovic,
    showLastNameZawadzki = showLastNameZawadzki,
    showMinEnergyOnly = showMinEnergyOnly,
    # qsort          = qsort,
    qlimit         = qlimit,
    pageNames      = pageNames,
    currentPage    = currentPage,
    errMsg         = errMsg,
    varMapHtml     = varMapHtml,
    tableHtml      = tableHtml,
    numTotal       = numTotal,
    sub_path       = request.route_path('rtQueryStd', queryRest='someRest'),
    authedSecure   = security.authenticated_userid( request),
    authedSession  = request.session.has_key('authedSession'),
    navList        = getNavList( request),
  )
# end vwQueryStd


#====================================================================

# QueryAdv

@view_config(route_name='rtQueryAdv', renderer='tmQueryAdv.mak',
  permission='permEdit')

def vwQueryAdv( request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  logIt('vwQueryAdv', request)

  queryFieldStg = settings['db_query_fields']
  queryFields = queryFieldStg.split()
  showFields = [nm.strip('*') for nm in queryFields if nm.endswith('*')]
  queryFields = map( lambda x: x.strip('*'), queryFields)

  if buglev >= 5:
    print 'vwQueryAdv: auth_userid: %s' \
      % (security.authenticated_userid( request),)
    print 'vwQueryAdv: route: %s' \
      % (request.route_url('rtQueryAdv', queryRest='someRest'),)
    print 'vwQueryAdv: path: %s' \
      % (request.route_path('rtQueryAdv', queryRest='someRest'),)
    print 'vwQueryAdv: current_route_url: %s' \
      % (request.current_route_url( queryRest='someRest'),)
    print 'vwQueryAdv: current_route_path: %s' \
      % (request.current_route_path( queryRest='someRest'),)
    print 'vwQueryAdv: matchdict: %s' % (request.matchdict,)
    print 'vwQueryAdv: matched_route: %s' % (request.matched_route,)
    print 'vwQueryAdv: GET: %s' % (request.GET,)
    print 'vwQueryAdv: POST: %s' % (request.POST,)

  dlmap = request.GET.dict_of_lists()
  if buglev >= 5:
    print 'vwQueryAdv: dlmap:'
    keys = dlmap.keys()
    keys.sort()
    for key in keys:
      print '  dlmap key: %s  value: %s' % (repr(key), repr(dlmap[key]),)
    print ''


  defHasAll = '''
    -- See 35.1, 39.1.
    CREATE OR REPLACE FUNCTION hasall(lsta text[], lstb text[])
      RETURNS boolean AS $$
    DECLARE
      res boolean;
    BEGIN
      -- array contains: See 9.18. Array Functions and Operators
      res := lsta @> lstb;
      RETURN res;
    END
    $$ LANGUAGE plpgsql;
  '''


  defHasNo = '''
    -- See 35.1, 39.1.
    CREATE OR REPLACE FUNCTION hasno(lsta text[], lstb text[])
      RETURNS boolean AS $$
    DECLARE
      res boolean;
    BEGIN
      -- overlap: See 9.18. Array Functions and Operators
      res := NOT (lsta && lstb);
      RETURN res;
    END
    $$ LANGUAGE plpgsql;
  '''

  columnDescs = getModelColDescs()
  descMap = getDescMap( 'model.', columnDescs)     # dbColName -> ColumnDesc

  pageStart = 0
  pageSize = 50

  db_rows = []
  errMsg = ''
  showCols = []
  showRows = []
  numTotal = 0
  pageNames = []
  currentPage = 0
  qlimit = 100
  qoffset = 0
  tableHtml = ''

  if dlmap.has_key('qexpr'):
    qexpr = dlmap['qexpr'][0].strip()
    qsort = dlmap['qsort'][0].strip()
    sortFields = qsort.split()
    for ii in range(len(sortFields)):   # translate tag to dbName
      nm = sortFields[ii]
      cdesc = None
      for cd in columnDescs:
        if cd.tag == nm:
          cdesc = cd
          break
      if cdesc == None:
        errMsg += 'unknown sort fields: "%s"<br>\n' % (nm,)
      else: sortFields[ii] = cdesc.dbName
    sortFields.append('mident')               # always sort on mident last

    # Set currentPage, qoffset from submitStg
    submitStgs = dlmap['submitQuery']
    submitStg = submitStgs[0].strip()
    if re.match('^\d+', submitStg):
      currentPage = int( submitStg) - 1            # origin 0
      qoffset = currentPage * qlimit

    if buglev >= 1:
      print 'vwQueryAdv: queryFields: %s' % (queryFields,)
      print 'vwQueryAdv: showFields: %s' % (showFields,)
      print 'vwQueryAdv: sortFields: %s' % (sortFields,)
      print 'vwQueryAdv: qexpr: %s' % (qexpr,)
      print 'vwQueryAdv: currentPage: %d' % (currentPage,)
      print 'vwQueryAdv: qoffset: %d' % (qoffset,)
      print 'vwQueryAdv: qlimit: %d' % (qlimit,)

    nameStg = ', '.join( queryFields)
    sortStg = ', '.join( sortFields)

    if qexpr == '': whereClause = 'true'
    else:
      (subErrMsg, whereClause) = rewriteQuery( qexpr)
      errMsg += subErrMsg

    query0 = 'set search_path to %s' % (settings['db_schema'],)

    query1 = defHasAll + defHasNo

    query2 = 'SELECT count(*) FROM model WHERE %s' % (whereClause,)

    query3 = 'SELECT %s FROM model WHERE %s ORDER BY %s LIMIT %s OFFSET %s' \
      % (nameStg, whereClause, sortStg, qlimit, qoffset,)

    queries = [query0, query1, query2, query3]
    dbRes = dbQuery( buglev, settings, queries)
    if type(dbRes).__name__ == 'str':
      errMsg += '%s<br>\n' % (dbRes,)
      numTotal = 0
      showCols = []
      showRows = []
    else:
      (msgs, colVecs, rowVecs) = dbRes
      numTotal = int( rowVecs[2][0][0])   # query 2, row 0, element 0
      db_rows = rowVecs[3]                # query 3
      for ii in range( 0, numTotal, qlimit):
        pageNames.append('%d' % (ii / qlimit + 1,))
      # Get icolMap: dbColName -> icol in queryFields
      icolMap = getIcolMap( descMap, queryFields)

      tableHtml = formatTableHtml(
        descMap, icolMap, showFields, colVecs, db_rows)

  else:
    ##qexpr = 'excMsg IS NULL and relaxType = \'std\' and 0 < bandgap and bandgap < 1.5 and minenergyid = mident'
    qexpr = '0 < bandgap and bandgap < 1.5 and hasall( zr si) and hasno( sb)'

    qsort = 'energyPerAtom bandgap icsdNum Id'

  ##if buglev >= 5: print 'vwQueryAdv: db_rows: %s' % (db_rows,)

  return dict(
    qexpr          = qexpr,
    qsort          = qsort,
    qlimit         = qlimit,
    pageNames      = pageNames,
    currentPage    = currentPage,
    errMsg         = errMsg,
    tableHtml      = tableHtml,
    numTotal       = numTotal,
    sub_path       = request.route_path('rtQueryAdv', queryRest='someRest'),
    authedSecure   = security.authenticated_userid( request),
    authedSession  = request.session.has_key('authedSession'),
    navList        = getNavList( request),
  )
# end vwQueryAdv


#====================================================================

# Detail

@view_config(route_name='rtDetail', renderer='tmDetail.mak',
  permission='permEdit')

def vwDetail(request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  if buglev >= 5: print 'vwDetail: auth_userid: %s' \
      % (security.authenticated_userid( request),)

  # Get map: dbname -> pair (cdesc, value)
  (errMsg, detailFields, dbMap) = getDbDetail( buglev, request, settings)

  db_pairs = []
  for nm in detailFields:
    pair = dbMap[nm]   # Get pair (cdesc, value)
    db_pairs.append( (pair[0].desc, pair[1]) )

  return dict(
    errMsg        = errMsg,
    db_pairs      = db_pairs,
    midentval     = dbMap['model.mident'][1],
    authedSecure  = security.authenticated_userid( request),
    authedSession = request.session.has_key('authedSession'),
    navList       = getNavList( request),
  )



#====================================================================

# DownloadSql

@view_config(route_name='rtDownloadSql', permission='permEdit')

def vwDownloadSql(request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  if buglev >= 5: print 'vwDownloadSql: auth_userid: %s' \
      % (security.authenticated_userid( request),)

  errMsg = ''
  dlmap = request.GET.dict_of_lists()
  if not dlmap.has_key('format'):
    errMsg += 'invalid request<br>\n'
  format = dlmap['format'][0]

  # Get map: dbname -> pair (cdesc, value)
  (subErrMsg, detailFields, dbMap) = getDbDetail( buglev, request, settings)
  errMsg += subErrMsg

  content = ''
  if errMsg == '':
    if format == 'python':
      keys = dbMap.keys()
      keys.sort()
      for key in keys:
        (cdesc, value) = dbMap[key]
        content += '%s = %s\n\n' % (cdesc.tag, repr( value),)
    elif format == 'json':
      keys = dbMap.keys()
      keys.sort()
      nuMap = {}
      for key in keys:
        (cdesc, value) = dbMap[key]
        nuMap[cdesc.tag] = value
      content = json.dumps( nuMap,
        indent = 2, separators=(',', ': '), sort_keys=True)
    else: errMsg += 'invalid format<br>\n'

  if errMsg != '':
    # xxx
    pass

  else:
    return pyramid.response.Response(
      body = content,
      content_type = 'text/plain',
    )


#====================================================================

# DownloadFlat

@view_config(route_name='rtDownloadFlat', permission='permEdit')

def vwDownloadFlat(request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  if buglev >= 5: print 'vwDownloadFlat: auth_userid: %s' \
      % (security.authenticated_userid( request),)

  errMsg = ''
  dlmap = request.GET.dict_of_lists()
  if not dlmap.has_key('format'):
    errMsg += 'invalid request<br>\n'
  format = dlmap['format'][0]

  # Get map: dbname -> pair (cdesc, value)
  (subErrMsg, detailFields, dbMap) = getDbDetail( buglev, request, settings)
  errMsg += subErrMsg

  archRoot = settings['archive_root']

  content = ''
  if errMsg == '':
    if format == 'tar.gz':
      dirPath = os.path.join(
        archRoot,
        dbMap['model.wrapid'][1],
        'vdir',
        dbMap['model.relpath'][1])
      names = os.listdir( dirPath)
      names.sort()
      keeps = []
      for name in names:
        path = os.path.join( dirPath, name)
        if os.path.isfile( path):
          keeps.append( name)

      svCwd = os.getcwd()
      try: 
        os.chdir( dirPath)
        fout = StringIO.StringIO()          # tar archive
        tar = tarfile.open( mode='w:gz', fileobj=fout)
        for keep in keeps:
          tar.add( keep)
        tar.close()
        content = fout.getvalue()
        fout.close()
      finally:
        os.chdir( svCwd)

    else: errMsg += 'invalid format: %s<br>\n' % (format,)

  if errMsg != '':
    # xxx we need an error template
    return pyramid.response.Response(
      body = '<h2>Error: %s</h2>' % (errMsg,),
      content_type = 'text/html',
    )

  else:
    response = pyramid.response.Response(
      body = content,
      content_type = 'application/x-gzip',
    )
    response.headerlist.append(
      ('Content-Disposition',
       'attachment; filename="nrelMatDb_%08d.tar.gz"' \
         % (dbMap['model.mident'][1],)))
    return response



#====================================================================

# Visualize

@view_config(route_name='rtVisualize', renderer='tmVisualize.mak',
  permission='permEdit')

def vwVisualize(request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  if buglev >= 5: print 'vwVisualize: auth_userid: %s' \
      % (security.authenticated_userid( request),)

  # Get map: dbname -> pair (cdesc, value)
  (errMsg, detailFields, dbMap) = getDbDetail( buglev, request, settings)

  basisMat = dbMap['model.finalbasismat'][1]
  posMat = dbMap['model.finaldirectposmat'][1]
  anames = dbMap['model.atomnames'][1]
  elementMap = xyzToSmol.getElementMap()

  atoms = []
  for ii in range(len(anames)):
    atomId = len( atoms)
    atoms.append( xyzToSmol.Atom(
      atomId,
      anames[ii],
      [ posMat[ii][0], posMat[ii][1], posMat[ii][2]],
      elementMap))

  xyzToSmol.addReflections( buglev, atoms, elementMap)

  distType = 'center'
  posScale = 1.0             # xxx
  bonds = []
  # Omit bonds for now
  #bonds = xyzToSmol.calcBonds( buglev, distType, posScale, basisMat, atoms)

  coordType = 'direct'

  description = dbMap['model.formula'][1]
  smolString = xyzToSmol.formatSmol( buglev, description, elementMap,
    coordType, posScale, basisMat, atoms, bonds)

  return dict(
    errMsg        = errMsg,
    midentval     = dbMap['model.mident'][1],
    formula       = dbMap['model.formula'][1],
    smolString    = smolString,
    authedSecure  = security.authenticated_userid( request),
    authedSession = request.session.has_key('authedSession'),
    navList       = getNavList( request),
  )


#====================================================================

# Contrib

@view_config(route_name='rtContrib', renderer='tmContrib.mak',
  permission='permEdit')

def vwContrib(request):
  settings = request.registry.settings
  buglev = int( settings['buglev'])
  if buglev >= 5: print 'vwContrib: auth_userid: %s' \
      % (security.authenticated_userid( request),)

  contribFieldStg = settings['db_contrib_fields']
  contribFields = contribFieldStg.split()
  showFields = [nm for nm in contribFields if nm.endswith('*')]
  contribFields = map( lambda x: x.strip('*'), contribFields)
  showFields = map( lambda x: x.strip('*'), showFields)

  dlmap = request.GET.dict_of_lists()
  if buglev >= 5:
    print 'vwContrib: dlmap:'
    keys = dlmap.keys()
    keys.sort()
    for key in keys:
      print '  dlmap key: %s  value: %s' % (repr(key), repr(dlmap[key]),)
    print ''

  errMsg = ''

  query0 = 'set search_path to %s' % (settings['db_schema'],)

  nameStg = ', '.join( contribFields)
  query1 = 'SELECT %s FROM contrib ORDER BY wrapid' % (nameStg,)

  queries = [query0, query1,]
  dbRes = dbQuery( buglev, settings, queries)
  if type(dbRes).__name__ == 'str':
    errMsg += '%s<br>\n' % (dbRes,)
    showCols = []
    showRows = []
  else:
    (msgs, colVecs, rowVecs) = dbRes
    db_rows = rowVecs[1]            # query 1
    db_cols = colVecs[1]            # query 1

    columnDescs = getContribColDescs()
    descMap = getDescMap('contrib.', columnDescs)   # dbColName -> ColumnDesc

    # Get icolMap: dbColName -> icol in queryFields
    icolMap = getIcolMap( descMap, contribFields)

    ncol = len( showFields)
    showCols = ncol * [None]

    nshowRow = len( db_rows)
    showRows = nshowRow * [None]

    for ii in range( nshowRow):
      showRows[ii] = ncol * [None]

    for jj in range( ncol):
      nm = showFields[jj]
      cdesc = descMap[ nm]
      showCols[jj] = cdesc.tag
      for ii in range( nshowRow):
        showRows[ii][jj] = db_rows[ii][icolMap[nm]]


  ##if buglev >= 5: print 'vwContrib: db_rows: %s' % (db_rows,)

  return dict(
    showCols       = showCols,
    showRows       = showRows,
    errMsg         = errMsg,
    authedSecure   = security.authenticated_userid( request),
    authedSession  = request.session.has_key('authedSession'),
    navList        = getNavList( request),
  )



#====================================================================


# Given a string like 'H2SO4',
# returns a list of pairs where each pair is (elementName, number),
# like [('H', 2), ('S', 1), ('O', 4)].
#
# We combine multiple identical elements and put in alphabetic order,
# so 'COOH C6H4 OCO CH3' becomes [('C',9), ('H',8), ('O',4)]
# (acetylsalicylic acid).
#
# It ignores spaces and commas.

def parseElements( stg):
  eleMap = {}
  ix = 0
  while ix < len(stg):
    if stg[ix] in ' ,':
      ix += 1
    else:
      ele = stg[ix]
      ix += 1
      if not ele.isupper():
        throwerr('element does not start with uppercase: "%s"' % (ele,))
      if ix < len(stg) and stg[ix].islower():
        ele += stg[ix]
        ix += 1
      if not ele in elementsStandard:
        throwerr('unknown element name: "%s"' % (ele,))

      neleStg = ''
      while ix < len(stg) and stg[ix].isdigit():
        neleStg += stg[ix]
        ix += 1
      if neleStg == '': nele = 1
      else: nele = int( neleStg)

      if not eleMap.has_key(ele): eleMap[ele] = 0
      eleMap[ele] += nele
  keys = eleMap.keys()
  keys.sort()
  pairs = [(key, eleMap[key]) for key in keys]
  return pairs


#====================================================================


def formatTableHtml(
  descMap,
  icolMap,
  showFields,
  colVecs,
  db_rows):

  icolIcsdnum = icolMap['model.icsdnum']

  ncol = len( showFields)
  showCols = ncol * [None]

  nshowRow = len( db_rows)
  showRows = nshowRow * [None]
  for ii in range( nshowRow):
    showRows[ii] = ncol * [None]

  for jj in range( ncol):
    nm = showFields[jj]
    icol = icolMap[nm]
    cdesc = descMap[ nm]
    showCols[jj] = cdesc.tag
    for ii in range( nshowRow):
      val = db_rows[ii][icol]
      if val == None: stg = 'null'
      else: stg = cdesc.fmt % val
      showRows[ii][jj] = stg

  fout = StringIO.StringIO()
  print >> fout, '<table style="border:2px solid gray; margin-left:0;'
  print >> fout, '  margin-right: auto;">'
  print >> fout, '<tr>'

  for col in showCols:
    print >> fout, '<th style="border:1px solid blue;'
    print >> fout, '  background-color:yellow">'
    print >> fout, col
    print >> fout, '</th>'
  print >> fout, '</tr>'

  for row in showRows:
    icMident = icolMap['model.mident']
    icMinEnergyId = icolMap['model.minenergyid']
    midentStg = row[icMident]
    minEnergyIdStg = row[icMinEnergyId]

    if midentStg == minEnergyIdStg:
      bgcolor = '#ffffc0' # row highlight color
    else: bgcolor = 'white'

    print >> fout, '<tr>'
    for icol in range( len( showCols)):
      col = showCols[icol]
      print >> fout, '  <td style="border-left: 3px solid white;'
      print >> fout, '    border-right: 3px solid white;'
      print >> fout, '    background-color: %s;">' % (bgcolor,)
      if icol == 0:
        print >> fout, '  <a href="detail?midentspec=%s">' % (row[0],)
      print >> fout, '    %s' % (row[icol],)
      if icol == 0:
        print >> fout, '  </a>'
      print >> fout, '  </td>'
    print >> fout, '  </tr>'

  print >> fout, '</table>'
  tableHtml = fout.getvalue()
  fout.close()

  return tableHtml

# end formatTable


#====================================================================


# Returns tuple: (errMsg, detailFields, dbMap)
# where dbMap is: dbName -> pair (cdesc, value)

def getDbDetail( buglev, request, settings):

  dlmap = request.GET.dict_of_lists()
  if buglev >= 5:
    print 'vwDetail: dlmap:'
    keys = dlmap.keys()
    keys.sort()
    for key in keys:
      print '  dlmap key: %s  value: %s' % (repr(key), repr(dlmap[key]),)
    print ''

  errMsg = ''

  if not dlmap.has_key('midentspec'):
    errMsg += 'invalid request<br>\n'
  midentstg = dlmap['midentspec'][0]
  try: midentval = int( midentstg)
  except Exception, exc:
    errMsg += 'invalid mident: %s<br>\n' % (midentstg,)


  query0 = 'set search_path to %s' % (settings['db_schema'],)

  query1 = 'SELECT icsdnum FROM model WHERE mident = %d' % (midentval,)

  queries = [query0, query1,]
  dbRes = dbQuery( buglev, settings, queries)

  dbMap = {}       # dbname -> value
  if type(dbRes).__name__ == 'str':
    errMsg += '%s<br>\n' % (dbRes,)
  else:
    (msgs, colVecs, rowVecs) = dbRes
    # Two queries create two sets of rows; should be 1 row in second query.
    if len(rowVecs) != 2 or len(rowVecs[1]) != 1:
      errMsg += 'mident not found: %d<br>\n' % (midentval,)
    else:
      db_row = rowVecs[1][0]          # query 1, row 0
      db_cols = colVecs[1]            # query 1
      icsdnum = db_row[0]
      if icsdnum == None:
        detailFieldStg = settings['db_general_detail_fields']
        detailFields = detailFieldStg.split()
        nameStg = ', '.join( detailFields)
        query1 = 'SELECT %s FROM model WHERE mident = %d' \
          % (nameStg, midentval,)
      else:
        detailFieldStg = settings['db_general_detail_fields'] \
          + ' ' + settings['db_icsd_detail_fields']
        detailFields = detailFieldStg.split()
        nameStg = ', '.join( detailFields)
        query1 = 'SELECT %s FROM model, icsd WHERE model.icsdnum = icsd.icsdnum AND mident = %d' \
          % (nameStg, midentval,)



  query0 = 'set search_path to %s' % (settings['db_schema'],)


  queries = [query0, query1,]
  dbRes = dbQuery( buglev, settings, queries)

  dbMap = {}       # dbname -> value
  if type(dbRes).__name__ == 'str':
    errMsg += '%s<br>\n' % (dbRes,)
  else:
    (msgs, colVecs, rowVecs) = dbRes
    # Two queries create two sets of rows; should be 1 row in second query.
    if len(rowVecs) != 2 or len(rowVecs[1]) != 1:
      errMsg += 'mident not found: %d<br>\n' % (midentval,)
    else:
      db_row = rowVecs[1][0]          # query 1, row 0
      db_cols = colVecs[1]            # query 1

      columnDescs = getModelColDescs()
      descMap = getDescMap( 'model.', columnDescs)    # dbColName -> ColumnDesc

      columnDescs = getIcsdColDescs()
      descMap.update( getDescMap( 'icsd.', columnDescs))

      # Get icolMap: dbColName -> icol in queryFields
      icolMap = getIcolMap( descMap, detailFields)

      for nm in detailFields:
        dbMap[nm] = ( descMap[nm], db_row[icolMap[nm]])

  return (errMsg, detailFields, dbMap)

# end getDbDetail



#====================================================================


def rewriteQuery( qexpr):

  # The query expression qexpr is like:
  #   bandgap >= 0.3 and hasall(cu fe) and hasno( h he)
  #
  # We convert this to
  #   bandgap >= 0.3 and hasall(typenames, ARRAY['Cu', 'Fe'])
  #     and hasno( typenames, ARRAY['H', 'He'])

  errMsg = ''
  toks = tokenize( varMap, qexpr)     # lex to lower case tokens

  # Handle hasall, hasno
  tagnames = ['hasall', 'hasno']
  for tagname in tagnames:
    itag = 0
    while itag < len(toks):
      # Find next occurance of tagname
      if tagname not in toks[itag:]: break
      itag = toks.index( tagname, itag)
      if itag+1 >= len(toks) or toks[itag+1] != '(':
        errMsg += 'invalid query: "%s"<br>\n' % (qexpr,)
      ii = itag + 2
      iend = None
      while ii < len(toks):
        if toks[ii] == ')':
          del toks[ii-1]         # delete the final comma
          iend = ii - 1
          break
        else:
          if toks[ii] not in elementsLower:
            errMsg += 'invalid query. ii: %d  tok: "%s"  toks: %s<br>\n' \
              % (ii, toks[ii], toks,)
          toks[ii] = toks[ii][0].upper() + toks[ii][1:]  # change bi to Bi
          toks[ii] = '\'%s\'' % (toks[ii],)      # add quotes: 'Bi'
          toks[ii+1:ii+1] = [',']                # insert comma
          ii += 2                                # skip over ele and comma
      if iend == None: errMsg += 'no close paren<br>\n'
      toks[itag+2:itag+2] = ['typenames', ',', 'ARRAY', '[']
      iend += 4
      toks[iend:iend] = [']']
      iend += 1

      itag = iend

  requery = ' '.join( toks)
  return (errMsg, requery)



#====================================================================


# Given list of queries, returns three parallel arrays:
#   (msgs, colVecs, rowVecs)
# where:
#   msgs[iquery]    = cursor.statusmessage for that query
#   colVecs[iquery] = list of col names for that query
#   rowVecs[iquery] = list of rows for that query
#
# But if there is an exception, we just return the exception.

def dbQuery( buglev, settings, queries):
  nquery = len( queries)
  msgs = nquery * [None]
  colVecs = nquery * [None]
  rowVecs = nquery * [None]

  conn = None
  cursor = None
  excMsg = None
  try:
    conn = psycopg2.connect(
      host=settings['db_host'],
      port=settings['db_port'],
      user=settings['db_user'],
      password=settings['db_pswd'],
      database=settings['db_name'])
    cursor = conn.cursor()

    for iquery in range( nquery):
      query = queries[iquery]
      if buglev >= 5:
        print '\ndbQuery: iquery: %d  query: %s' % (iquery, query,)

      cursor.execute( query)

      msgs[iquery] = cursor.statusmessage
      if query.startswith('select ') or query.startswith('SELECT '):
        colVecs[iquery] = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        # Convert rows from tuples to lists so we can modify them later
        for irow in range(len(rows)):
          rows[irow] = list( rows[irow])
        rowVecs[iquery] = rows
  except Exception, exc:
    print 'dbquery: caught: %s' % (exc,)
    excMsg = str( exc)
  finally:
    if cursor != None: cursor.close()
    if conn != None: conn.close()

  if buglev >= 1:
    if excMsg != None:
      print 'dbQuery: excMsg: %s' % (excMsg,)
    else:
      for ii in range(len(queries)):
        print 'dbQuery: queries[%d]:'
        print '  queries[ii]: %s' % (queries[ii],)
        print '  msgs[ii]: %s' % (msgs[ii],)
        if colVecs[ii] == None:
          print '  colVecs[ii]): None'
        else:
          print '  len(colVecs[ii]): %s' % (len(colVecs[ii]),)
        if rowVecs[ii] == None:
          print '  rowVecs[ii]): None'
        else:
          print '  len(rowVecs[ii]): %s' % (len(rowVecs[ii]),)

  if excMsg != None: res = excMsg
  else: res = (msgs, colVecs, rowVecs)
  return res


#====================================================================


# Returns descMap: colName -> ColumnDesc

def getDescMap( prefix, columnDescs):
  # Check that dbName is lower case
  for cdesc in columnDescs:
    dnm = cdesc.dbName
    if dnm.lower() != dnm:
      throwerr('dbName must be lower case: "%s"' % (dnm,))

  # Fill descMap
  descMap = {}
  for cdesc in columnDescs:
    descMap[ prefix + cdesc.dbName] = cdesc

  return descMap


#====================================================================

# Returns icolMap: dbColName -> icol in queryFields

def getIcolMap( descMap, queryFields):

  # Fill icolMap
  icolMap = {}
  for icol in range(len(queryFields)):
    nm = queryFields[icol]
    if not descMap.has_key(nm):
      throwerr('views.py: getIcolMap: unknown col name: "%s"' % (nm,))
    if icolMap.has_key(nm): throwerr('duplicate col name: "%s"' % (nm,))
    icolMap[nm] = icol

  return icolMap


#====================================================================


# We tokenize operators, numbers, quoted strings,
# sqlKeywords, and varMap identifiers.
#
# We convert:
#   sqlKeywords to uppercase.
#   varMap keys(userNames) to varMap values(dbNames)

def tokenize(
  varMap,      # userVarName -> dbVarName
  stg):

  varKeys = varMap.keys()
  sqlKeywords = ['and', 'or', 'not']

  toks = []
  while True:
    stg = stg.strip()
    if len(stg) == 0: break
    # Handle operators first so -3 gets split to '-', '3'
    # and 3.e-5 stays together.
    ops = ['(', ')',
      '+', '-', '*', '/',
      '<=', '>=', '<', '>',   # must have <= before <, and similarly for >=, >
      '=', '!=']

    isFound = False
    for op in ops:
      if stg.startswith( op):
        toks.append( op)
        stg = stg[len(op):]
        isFound = True
        break

    # Check for numbers
    if not isFound:
      mat = re.match(r'^([0-9]+(.[0-9]*)?(e-?[0-9]+)?)', stg)
      if mat:
        tok = mat.group(1)
        toks.append( tok)
        stg = stg[len(tok):]
        isFound = True

    # Check for quoted strings
    if not isFound and stg.startswith('\''):
      iend = stg.find('\'', 1)
      if iend < 0: throwerr('invalid query: stg: "%s"' % (stg,))
      tok = stg[:iend+1]
      toks.append( tok)
      stg = stg[len(tok):]
      isFound = True

    # Check for sqlKeywords and variables
    if not isFound:
      mat = re.match(r'^([a-zA-Z]+)', stg)
      if mat:
        tok = mat.group(1)
        if tok in sqlKeywords: val = tok.upper()
        elif tok in varKeys: val = varMap[tok]
        else: throwerr('invalid query: token: "%s"  stg: "%s"' % (tok, stg,))

        toks.append( val)
        stg = stg[len(tok):]
        isFound = True

    if not isFound:
      throwerr('invalid query: "%s"' % (stg,))

  return toks


#====================================================================


def logIt( msg, request):
  buglev = int( request.registry.settings['buglev'])
  if buglev >= 1:
    print '%s  mthd: %s  url: %s  hver: %s' \
        % (msg, request.method, request.url, request.http_version,)
  return


#====================================================================


def throwerr( msg):
  raise Exception( msg)

#====================================================================
