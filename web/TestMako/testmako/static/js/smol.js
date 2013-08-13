
console.log("main script start");




var mouseHandler;
function mouseHandler( event) {
  if (false) {
    console.log('mouseHandler:'
      + '  button: ' + event.button
      + '  buttons: ' + event.buttons
      + '  which: ' + event.which
      + '  clientX: ' + event.clientX
      + '  clientY: ' + event.clientY
      + '  pageX: ' + event.pageX
      + '  pageY: ' + event.pageY
      + '  camera x: ' + camera.position.x);
  }
  //for (var nm in event) {
  //  console.log('    ' + nm + '  ' + event[nm]);
  //}
  //camera.position.x += 0.01;
  camera.rotation.z += 0.01;
  update();
}






var ElementObj;
function ElementObj( esym, eradius, ecolor) {
  if (this.constructor.name !== 'ElementObj') throwerr('missing new');
  this.esym = esym;
  this.eradius = eradius;
  this.ecolor = ecolor;
  this.toString = function() {
    var colHex = this.ecolor.toString(16);
    while (colHex.length < 6) {
      colHex = '0' + colHex;
    }
    var res = 'ElementObj:'
      + '  esym: ' + String( this.esym)
      + '  eradius: ' + String( this.eradius)
      + '  ecolor hex: ' + colHex;
    return res;
  }
}


// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/toString





var time0 = (new Date()).getTime();
var noteTimes = [];

var pushTime;
function pushTime( msg) {
  var timeb = (new Date()).getTime();
  noteTimes.push( [ msg, timeb]);
}


var printTimes;
function printTimes() {
  console.log('\nprintTimes:\n');
  var timea = time0;
  for (var ii = 0; ii < noteTimes.length; ii++) {
    var pair = noteTimes[ii];
    var msg   = pair[0];
    var timeb = pair[1];
    var deltaTime = 0.001 * (timeb - timea);
    var cumTime = 0.001 * (timeb - time0);
    while (msg.length < 20)
      msg += ' ';
    console.log( msg + '  delta: ' + deltaTime.toFixed(4)
      + '  cum: ' + cumTime.toFixed(4));
    timea = timeb;
  }
}


var init;
function init() {
  pushTime('init A');
  buglev = 1;


  // Offset of center of unit cube from the origin, in each dimension.
  var aoffset = 0.5;

  // SCENE
  scene = new THREE.Scene();

  // CAMERA
  var screenWidth = window.innerWidth;
  var screenHeight = window.innerHeight;
  var aspectRatio = screenWidth / screenHeight;
  var viewAngle = 45;
  //camera = new THREE.PerspectiveCamera(
  //  viewAngle, aspectRatio, 0.1, 10000);   // nearBound, farBound
  //camera = new THREE.OrthographicCamera(
  //  -0.5 * screenWidth, 0.5 * screenWidth,        // left, right
  //  0.5 * screenHeight, -0.5 * screenHeight,      // top, bottom
  //  0.1, 10000);       // nearBound, farBound
  //scene.add(camera);
  //camera.position.set( 0, 0, 2);
  // Camera.lookat doesn't work because the TrackballControls
  // overrides it.
  // So we have to move our scene to the origin.
  //camera.lookAt( new THREE.Vector3( aoffset, aoffset, aoffset));

  camera = new THREE.OrthographicCamera(
    -0.7, 0.7,         // left, right
    0.7, -0.7,         // top, bottom
    0.1, 10000);       // nearBound, farBound
  scene.add(camera);
  camera.position.set( 0, 0, 100);

  // RENDERER
  if (Detector.webgl)
    renderer = new THREE.WebGLRenderer( {antialias:true} );
  else
    renderer = new THREE.CanvasRenderer(); 
  renderer.setSize( screenWidth, screenHeight);
  renderer.setClearColorHex( 0x000000, 1);    // Set background color = black
 
  //container = document.getElementById('container');
  container = document.createElement( 'div' );
  document.body.appendChild( container );

  container.appendChild( renderer.domElement );

  // EVENTS
  //THREEx.WindowResize(renderer, camera);
  //THREEx.FullScreen.bindKey({ charCode : 'm'.charCodeAt(0) });

  // STATS
  //stats = new Stats();
  //stats.domElement.style.position = 'absolute';
  //stats.domElement.style.bottom = '0px';
  //stats.domElement.style.zIndex = 100;
  //container.appendChild( stats.domElement );

  // LIGHT

  var light2 = new THREE.AmbientLight(0xffffff);
  scene.add(light2);
  
  var light3 = new THREE.DirectionalLight(0xffffff, 1.0, 0);
  scene.add(light3);
  
  ////////////
  // CUSTOM //
  ////////////

  var containera = new THREE.Object3D();

  //containera.position = new THREE.Vector3( 0, 0, 0);
  containera.position.set( 0, 0, 0.0001);
  containera.rotation.set( 0, 0, 0);
  console.log('camera.position:     ', camera.position);
  console.log('scene.position:      ', scene.position);
  console.log('containera.position: ', containera.position);


  console.log('\n========== start read atomInfo ==========\n');

  if (typeof atomInfoXyzId === 'string') {
    console.log('========== start read atomInfoXyzId ==========');
    var atomInfo = parseXyz( getDocTextLines( atomInfoXyzId));
  }
  else if (typeof atomInfoCmlFile === 'string') {
    console.log('========== start read atomInfoCmlFile ==========');
    var atomInfo = parseCml( readRemoteXmlDom( atomInfoCmlFile));
  }
  else if (typeof atomInfoSmolId === 'string') {
    console.log('========== start read atomInfoSmolId ==========');
    var atomInfo = parseSmol( getDocTextContent( atomInfoSmolId));
  }
  else if (typeof atomInfoSmolFile === 'string') {
    console.log('========== start read atomInfoSmolFile ==========');
    var atomInfo = parseSmol( readRemoteFileContent( atomInfoSmolFile));
  }
  else throwerr('no atomInfo specified')

  pushTime('read atomInfo');

  var atoms = atomInfo.atoms;
  var basisMat = atomInfo.basisMat;
  var bonds = atomInfo.bonds;
  var coordType = atomInfo.coordType;
  var description = atomInfo.description;
  var elementMap = atomInfo.elementMap;
  var posScale = atomInfo.posScale;

  if (buglev >= 5) {
    for (var ii = 0; ii < atoms.length; ii++) {
      console.log('init: atoms[%d]:\n%s', ii, formatAtom( atoms[ii]));
    }
  }

  console.log('init: basisMat: %s', basisMat);
  console.log('init: bonds: %s', bonds);
  console.log('init: coordType: %s', coordType);
  console.log('init: description: %s', description);
  console.log('init: elementMap: %s', elementMap);
  console.log('init: posScale: %s', posScale);

  // Validate everything
  if (typeof atoms !== 'object'
    || typeof atoms.length != 'number'
    || atoms.length < 1)
    throwerr('invalid atoms: '+ atoms);
  // Check that each atom has: aix==ii, asym, directCoords
  for (var ii = 0; ii < atoms.length; ii++) {
    var atom = atoms[ii];
    if (atom.aix !== ii)
      throwerr('invalid aix in atom: ' + atom);
    if (typeof atom.asym !== 'string')
      throwerr('invalid asym in atom: ' + atom)
    if (typeof atom.directCoords != 'object'
      || typeof atom.directCoords.length != 'number'
      || atom.directCoords.length != 3
      || typeof atom.directCoords[0] != 'number')
      throwerr('invalid directCoords in atom: ' + atom)
  }

  if (typeof basisMat != 'object'
    || typeof basisMat.length != 'number'
    || basisMat.length != 3
    || typeof basisMat[0].length != 'number' || basisMat[0].length != 3
    || typeof basisMat[1].length != 'number' || basisMat[1].length != 3
    || typeof basisMat[2].length != 'number' || basisMat[2].length != 3
    || typeof basisMat[0][0] != 'number')
    throwerr('invalid basisMat: ' + basisMat)

  basisMat = new THREE.Matrix3(
    basisMat[0][0], basisMat[0][1], basisMat[0][2],
    basisMat[1][0], basisMat[1][1], basisMat[1][2],
    basisMat[2][0], basisMat[2][1], basisMat[2][2]);

  if (typeof bonds !== 'object'
    || typeof atoms.length != 'number')
    throwerr('invalid bonds: '+ bonds);
  if (bonds.length >= 1
    && ( typeof bonds[0] != 'object'
      || typeof bonds[0].length != 'number'
      || bonds[0].length != 2))
    throwerr('invalid bonds: '+ bonds);

  if (typeof coordType !== 'string'
    || (coordType != 'direct' && coordType != 'cartesian'))
    throwerr('invalid coordType: '+ coordType);

  if (typeof description !== 'string')
    throwerr('invalid description: '+ description);

  if (typeof elementMap !== 'object'
    || typeof Object.keys( elementMap).length != 'number'
    || Object.keys( elementMap).length < 1)
    throwerr('invalid elementMap: '+ elementMap);

  if (typeof posScale !== 'number'
    || posScale < 0.001
    || posScale > 1000)
    throwerr('invalid posScale: '+ posScale);



  var atomMap  = getAtomMap( atoms)

  // Direct coord corners
  var corners = getCorners( aoffset, coordType, posScale, basisMat);

  // Calc corners = cartesian( corners)
  var basisMatTranspose = basisMat.clone();
  basisMatTranspose.transpose();

  // Find min, max of all cartesian coords.
  var minCartVec = new THREE.Vector3( Infinity,  Infinity,  Infinity);
  var maxCartVec = new THREE.Vector3(-Infinity, -Infinity, -Infinity);
  if (corners !== null) {
    for (var ii = 0; ii < 2; ii++) {
      for (var jj = 0; jj < 2; jj++) {
        for (var kk = 0; kk < 2; kk++) {
          console.log('######### direct corner: ', corners[ii][jj][kk].x,
            corners[ii][jj][kk].y, corners[ii][jj][kk].z);
          corners[ii][jj][kk] = directToCartesian(
            posScale, basisMatTranspose, corners[ii][jj][kk]);
          minCartVec.min( corners[ii][jj][kk]);
          maxCartVec.max( corners[ii][jj][kk]);
          console.log('cartesian corners[%d][%d][%d]: %s',
            ii, jj, kk, formatVector3( corners[ii][jj][kk]));
        }
      }
    }
  }
  var rangeCartVec = maxCartVec.clone();
  rangeCartVec.sub( minCartVec);
  console.log('corners minCartVec: %s', formatVector3( minCartVec));
  console.log('corners maxCartVec: %s', formatVector3( maxCartVec));
  console.log('corners rangeCartVec: %s', formatVector3( rangeCartVec));

  // Set atom projections:
  //   cartCoordVec = posScale * basisMatTranspose * directCoords
  //   projCoordVec = (cartCoordVec - mins) / ranges - aoffset

  for (var ii = 0; ii < atoms.length; ii++) {
    var atom = atoms[ii];
    var directVec = new THREE.Vector3(
      atom.directCoords[0],
      atom.directCoords[1],
      atom.directCoords[2]);
    console.log('######### direct atom: ', directVec.x,
      directVec.y, directVec.z);
    atom.cartCoordVec = directToCartesian(
      posScale, basisMatTranspose, directVec);
  }

  if (atoms.length == 0) {}
  else if (atoms.length == 1) {
    atoms[0].projCoordVec = new THREE.Vector3( 0, 0, 0);
  }
  else {
    // Calc projection onto display cube for the atoms
    for (var ii = 0; ii < atoms.length; ii++) {
      atom = atoms[ii];
      minCartVec.min( atom.cartCoordVec);
      maxCartVec.max( atom.cartCoordVec);
    }
    rangeCartVec = maxCartVec.clone();
    rangeCartVec.sub( minCartVec);
    console.log('atoms minCartVec: %s', formatVector3( minCartVec));
    console.log('atoms maxCartVec: %s', formatVector3( maxCartVec));
    console.log('atoms rangeCartVec: %s', formatVector3( rangeCartVec));

    // x = (x - xmin) / xrange
    for (var ii = 0; ii < atoms.length; ii++) {
      atom = atoms[ii];
      atom.projCoordVec = cartesianToProjection(
        aoffset, minCartVec, rangeCartVec, atom.cartCoordVec);
    }
  }
  console.log('===== getAtomCoordVecs: end.  atoms[0]:\n%s',
    formatAtom( atoms[0]));


  // Calc projection onto display cube for the corners
  if (corners !== null) {
    for (var ii = 0; ii < 2; ii++) {
      for (var jj = 0; jj < 2; jj++) {
        for (var kk = 0; kk < 2; kk++) {
          corners[ii][jj][kk] = cartesianToProjection(
            aoffset, minCartVec, rangeCartVec, corners[ii][jj][kk]);
          console.log('projection corners[%d][%d][%d]: %s',
            ii, jj, kk, formatVector3( corners[ii][jj][kk]));
        }
      }
    }
  }



  for (var ii = 0; ii < atoms.length; ii++) {
    console.log('init: mod atoms[%d]:\n%s', ii, formatAtom( atoms[ii]));
  }

  // Validate atoms a bit more
  for (var ii = 0; ii < atoms.length; ii++) {
    var atom = atoms[ii];
    if (typeof atom.cartCoordVec !== 'object'
      || ! isFinite( atom.cartCoordVec.x)
      || ! isFinite( atom.cartCoordVec.y)
      || ! isFinite( atom.cartCoordVec.z))
      throwerr('invalid cartCoordVec in atom: ' + atom)
    if (typeof atom.projCoordVec !== 'object'
      || ! isFinite( atom.projCoordVec.x)
      || ! isFinite( atom.projCoordVec.y)
      || ! isFinite( atom.projCoordVec.z))
      throwerr('invalid projCoordVec in atom: ' + atom)
  }




  var drawLine = function( containera, color, veca, vecb) {
    var lineGeom = new THREE.Geometry();
    lineGeom.vertices.push( veca);
    lineGeom.vertices.push( vecb);
    var lineMaterial = new THREE.LineBasicMaterial(
      { color: color, opacity: 1, linewidth: 1 } );
    var line = new THREE.Line( lineGeom, lineMaterial );
    containera.add(line);
  }




  // Display unit cell edges
  console.log('init: begin draw unit cell edges')
  if (corners !== null) {
    // Bottom face
    drawLine( containera, 0xff0000, corners[0][0][0], corners[1][0][0]);
    drawLine( containera, 0xff0000, corners[1][0][0], corners[1][1][0]);
    drawLine( containera, 0xff0000, corners[1][1][0], corners[0][1][0]);
    drawLine( containera, 0xff0000, corners[0][1][0], corners[0][0][0]);
    // Top face
    drawLine( containera, 0xff0000, corners[0][0][1], corners[1][0][1]);
    drawLine( containera, 0xff0000, corners[1][0][1], corners[1][1][1]);
    drawLine( containera, 0xff0000, corners[1][1][1], corners[0][1][1]);
    drawLine( containera, 0xff0000, corners[0][1][1], corners[0][0][1]);
    // Vertical edges
    drawLine( containera, 0xff0000, corners[0][0][0], corners[0][0][1]);
    drawLine( containera, 0xff0000, corners[1][0][0], corners[1][0][1]);
    drawLine( containera, 0xff0000, corners[0][1][0], corners[0][1][1]);
    drawLine( containera, 0xff0000, corners[1][1][0], corners[1][1][1]);
  }
  console.log('init: end draw unit cell edges')


  // Display bonds

  console.log('init: begin draw bonds')
  for (var ii = 0; ii < bonds.length; ii++) {
    var bond = bonds[ii]
    var atoma = atomMap[bond[0]];
    var atomb = atomMap[bond[1]];
    var useCyl = false;
    makeBond( useCyl, atoma, atomb, containera);
  }
  console.log('init: end draw bonds')
  pushTime('mk bonds');



  // Display atoms

  console.log('init: begin draw atoms')
  for (var ispec = 0; ispec < atoms.length; ispec++) {
    var atom = atoms[ispec];

    var texUrl = 'static/images/element.' + atom.asym + '.png';
    //console.log('texUrl: ', texUrl);
    var tex = THREE.ImageUtils.loadTexture( texUrl, null, null, throwerr);
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.x = 4;
    tex.repeat.y = 1;

    var mata = new THREE.MeshLambertMaterial(
      { map: tex, color: elementMap[atom.asym].ecolorHex,
        ambient: elementMap[atom.asym].ecolorHex,
        side: THREE.DoubleSide } );
    //var mata = new THREE.MeshBasicMaterial(
    //  { map: tex, color: 0x00ff00 } );

    var radiusFactor = 0.0007;
    var radius = radiusFactor * elementMap[atom.asym].eradiusAtomic_pm;
    radius = 0.07;    // Fixed radius
    var sphereGeom =  new THREE.SphereGeometry(
      radius, 16, 16);        // radius, widthSegments, heightSegments

    var sphereMesh = new THREE.Mesh( sphereGeom.clone(), mata );

    sphereMesh.position.copy( atom.projCoordVec);
    //console.log('sphere pos: ', sphereMesh.position);
    containera.add( sphereMesh );  
  }
  console.log('init: end draw atoms')
  pushTime('mk atoms');





  var drawArrow = function( tag, veca, vecb, color) {
    var vecd = vecb.clone();
    vecd.sub( veca);             // unnormalized direction
    var vecdn = vecd.clone();
    vecdn.normalize();           // normalized direction

    var arrow = new THREE.ArrowHelper(
      vecdn,                 // normalized direction
      veca,                  // origin
      0.5 * vecd.length(),   // len = half of unnormalized distance
      color);
    arrow.transparent = true;
    arrow.opacity = 0.5;
    containera.add( arrow);

    var textGeom = new THREE.TextGeometry(
      tag,
      {size: 0.05,
      height: 0.001,
      face: 'helvetiker',
      weight: 'normal',
      style: 'normal',
      divisions: 10});
    var textMaterial = new THREE.MeshLambertMaterial(
      { color: color,
        ambient: color,
        transparent: false,
        opacity: 1.0,
        side: THREE.DoubleSide});
    var textMesh = new THREE.Mesh( textGeom.clone(), textMaterial);
    textMesh.position.copy( veca);
    textMesh.position.add( vecb);
    textMesh.position.multiplyScalar( 0.5);
    textMesh.position.x -= 0.05;
    textMesh.position.y -= 0.05;
    textMesh.position.z -= 0.05;
    containera.add( textMesh);
  }

  drawArrow( 'x', corners[0][0][0], corners[1][0][0], 0xff0000);
  drawArrow( 'y', corners[0][0][0], corners[0][1][0], 0xff0000);
  drawArrow( 'z', corners[0][0][0], corners[0][0][1], 0xff0000);

  //drawArrow( 'X',
  //  new THREE.Vector3( -aoffset,       -aoffset,       -aoffset),
  //  new THREE.Vector3( -aoffset + 0.5, -aoffset,       -aoffset),
  //  0x40ff40);
  //drawArrow( 'Y',
  //  new THREE.Vector3( -aoffset,       -aoffset,       -aoffset),
  //  new THREE.Vector3( -aoffset,       -aoffset + 0.5, -aoffset),
  //  0x40ff40);
  //drawArrow( 'Z',
  //  new THREE.Vector3( -aoffset,       -aoffset,       -aoffset),
  //  new THREE.Vector3( -aoffset,       -aoffset,       -aoffset + 0.5),
  //  0x40ff40);

  pushTime('mk arrows');


  console.log('containera done');

  scene.add( containera);


  controls = new THREE.TrackballControls( camera );
  pushTime('mk controls');

  printTimes();
} // end function init









var makeBond;
function makeBond( useCyl, atoma, atomb, containera) {

  var buglev = 0;
  if (buglev >= 5) {
    console.log('makeBond: atoma: %s', formatAtom( atoma))
    console.log('makeBond: atomb: %s', formatAtom( atomb))
  }
  var avec = atoma.projCoordVec;
  var bvec = atomb.projCoordVec;

  if (useCyl) {
    // dvec = bvec - avec = desired axis of cylinder
    var dvec = new THREE.Vector3();
    dvec.subVectors( bvec, avec);

    var dlen = dvec.length();

    // The cylinder is parallel to the y axis.
    // The center of the cylinder height, not the base, is at 0,0,0.
    var cylGeom = new THREE.CylinderGeometry(
      0.02,         // topRadius
      0.02,         // bottomRadius
      dlen,         // height
      64, 16,       // radiusSegments, heightSegments
      false);       // openEnded
    var cylMaterial = new THREE.MeshLambertMaterial(
      { color: 0x808080,
        ambient: 0x808080,
        transparent: false,
        opacity: 1.0,
        side: THREE.FrontSide});
    var cylMesh = new THREE.Mesh( cylGeom.clone(), cylMaterial);

    // yvec = y axis = axis of cylinder when created
    var yvec = new THREE.Vector3( 0, 1, 0);

    // Calc axis and angle to rotate yvec into dvec
    var angle = yvec.angleTo( dvec);        // = acos( dot(y,d) / (|y| * |d|))
    var axis = new THREE.Vector3();
    axis.crossVectors( yvec, dvec);         // axis = yvec x dvec
    axis.normalize();
    var rotMat = new THREE.Matrix4;
    rotMat.makeRotationAxis( axis, angle);

    cylMesh.matrix.multiply( rotMat);      // post-multiply
    cylMesh.rotation.setEulerFromRotationMatrix( cylMesh.matrix);

    // cylMesh.position = average( avec, bvec)
    cylMesh.position.addVectors( avec, bvec);
    cylMesh.position.multiplyScalar( 0.5);

    printObj('cylMesh A:', cylMesh);

    containera.add( cylMesh);
  }
  else {
    var buglev = 5;
    var lineGeom = new THREE.Geometry();
    lineGeom.vertices.push( avec);
    lineGeom.vertices.push( bvec);
    // xxx change bond line width with zoom == 1/5 min molec diam?
    // xxx Or 1/5 angstrom?
    var lineMaterial = new THREE.LineBasicMaterial(
      { color: 0x606060, opacity: 1, linewidth: 10 } );
    var line = new THREE.Line( lineGeom, lineMaterial );
    containera.add(line);
  }
} // end function makeBond




// xxx mark reflection atoms somehow
// xxx maybe two images: K and K'










var animate;
function animate() 
{
  requestAnimationFrame( animate );
  render();    
  update();
}



var update;
function update()
{
  //if ( keyboard.pressed('z') ) 
  //{ 
  //  // do something
  //}
  
  controls.update();
  //stats.update();
}



var render;
function render() 
{
  renderer.render( scene, camera );
}



var printObj;
function printObj( tag, obj) {
  console.log( '%s:', tag);
  if (obj.position) {
    console.log('  Position:  %f  %f  %f',
      obj.position.x,
      obj.position.y,
      obj.position.z);
  }

  var mat = obj.matrix;
  if (mat) {
    for (var ii = 0; ii < 4; ii++) {
      msg = '';
      for (var jj = 0; jj < 4; jj++) {
        msg += '  ' + mat.elements[4 * ii + jj];
      }
      console.log('    %s', msg);
    }
  }
}



// Rotate an object around an axis in object space
var rotateAroundObjectAxis;
function rotateAroundObjectAxis( object, axis, radians ) {
  var rotationMatrix = new THREE.Matrix4();
  rotationMatrix.makeRotationAxis( axis.normalize(), radians );
  console.log('=========== mat:', object.matrix);
  object.matrix.multiply( rotationMatrix ); // post-multiply
  object.rotation.setEulerFromRotationMatrix(object.matrix, object.order);
}




 
// Rotate an object around an axis in world space
// (the axis passes through the object's position)
var rotateAroundWorldAxis;
function rotateAroundWorldAxis( object, axis, radians ) {
  var rotWorldMatrix = new THREE.Matrix4();
  rotWorldMatrix.makeRotationAxis( axis.normalize(), radians);
  rotWorldMatrix.multiply(object.matrix); // pre-multiply
  object.matrix = rotWorldMatrix;
  object.rotation.setEulerFromRotationMatrix(object.matrix, object.order);
}




// Returns [atoms], with aid = index num starting at 0.
// Example:
//   var atomInfo = parseXyz( getDocTextLines( 'icsd_098129.xyz'));

var parseXyz;
function parseXyz( tlines) {
  console.log('\n========== start parseXyz ==========\n');
  var buglev = 5;
  //console.log('===== tlines:', tlines, '=====');

  var doc_nline = tlines.length;
  if (buglev >= 1) {
    console.log('===== doc_nline', doc_nline);
    console.log('===== tlines.length:', tlines.length);
  }
  if (doc_nline < 3) throwerr('doc_nline < 3');

  doc_natom = parseInt( tlines[0], 10);
  if (buglev >= 1) console.log('===== doc_natom', doc_natom);

  if (doc_nline !== doc_natom + 2) throwerr('doc_natom mismatch');
  description = tlines[1];
  console.log('===== description: ', description);
  atoms = [];
  for (var ii = 0; ii < doc_natom; ii++) {
    var line = tlines[2+ii];
    //console.log('===== line', line);
    var toks = line.split(/ +/);
    //console.log('===== toks', toks);
    if (toks.length !== 4) throwerr('wrong num coords');
    var asym = toks[0];
    var coords = [];
    for (var jj = 0; jj < 3; jj++) {
      coords.push( parseFloat( toks[1+jj]));
    }
    atoms.push( {
      aix: ii,
      asym: asym,
      directCoords: coords
    });
    if (buglev >= 1) {
      console.log('===== parseXyz: atoms[', ii, ']:', atoms[ii]);
    }
  }

  var atomMap = {};
  for (var ii = 0; ii < atoms.length; ii++) {
    atom = atoms[ii]
    atomMap[atom.aid] = atom
  }
  console.log('\nparseXyz: atomMap:', atomMap)

  var atomInfo = {
    description: description,
    atoms:       atoms,
    bonds:       [],             // no bonds in xyz format
    elementMap:  eleMap,
    atomMap:     atomMap,
    corners:     null};

  console.log('\n========== end parseXyz ==========\n');
  return atomInfo;
} // end parseXyz







var parseCml;
function parseCml( xmlDom) {
  console.log('\n========== start parseCml ==========\n');

  console.log('xmlDom: ', xmlDom);

  // Get atom info
  console.log('\n========== start get atom info ==========\n');

  // Namespace Resolvers
  // There are 3 ways to make namespaces work.
  //   1. No nsResolver.
  //   2. Call createNSResolver.
  //   3. Custom nsResolver.
  //
  // See: 
  //   https://developer.mozilla.org/en-US/docs/Introduction_to_using_XPath_in_JavaScript
  //   https://developer.mozilla.org/en-US/docs/Introduction_to_using_XPath_in_JavaScript#Implementing_a_User_Defined_Namespace_Resolver

  // Using Xpath with namespaces:
  //   A. var apath = '//*[local-name()=\'molecule\']';  // works w namespaces
  //   B. var apath = '*[local-name()=\'molecule\']';    // works w namespaces
  //   C. var apath = '*[name()=\'molecule\']';          // works w namespaces
  //   D. var apath = '/molecule/atomArray/atom';     // fails with namespaces
  //   E. var apath = 'molecule';                     // fails with namespaces
  //   F. var apath = 'child::molecule';              // fails with namespaces
  //
  // See: 
  // http://stackoverflow.com/questions/3931817/xpath-expression-from-xml-with-namespace-prefix
  //   /*/*[name()='bk:Books']/*[name()='bk:Book' and text()='Time Machine']
  //   /*/*[local-name()='Books']
  // http://stackoverflow.com/questions/7257088/xpath-xml-file-with-namespaces-using-javascript


  // Method 1: No nsResolver.
  //var nsResolverA = null;

  // Method 2: Call createNSResolver.
  var nsResolverA = xmlDom.createNSResolver( xmlDom.documentElement);
  console.log('nsResolverA: ', nsResolverA);
  console.log('nsResolverA result a: ', nsResolverA.lookupNamespaceURI(''));

  // Method 3: Custom nsResolver.
  var nsResolverB = function( prefix) {
    var res;
    if (prefix === '') res = 'http://www.xml-cml.org/schema';
    else throwerr('unknown namespace');
    return res;
  }
  console.log('nsResolverB: ', nsResolverB);
  console.log('nsResolverB result: ', nsResolverB(''));

  // Use method A of Xpath with namespaces.

  // Get description from molecule@id
  var apath = '/*[local-name()=\'molecule\']';      // works with namespaces

  var ares = xmlDom.evaluate(
    apath,                                    // xpath
    xmlDom,                                   // context node
    nsResolverA,                              // namespaceResolver
    XPathResult.FIRST_ORDERED_NODE_TYPE,   // resultType
    null);                                    // result
  // Caution Javascript language weirdness and kluge.
  // The resulting ares is undefined, but has singleNodeValue.
  console.log('  desc ares: ', ares);
  var anode = ares.singleNodeValue;
  console.log('  desc anode: ', anode);
  var description = anode.getAttribute('id');
  console.log('  description: ', description);

  // Get atoms from molecule/atomArray/atom
  var apath = '/*[local-name()=\'molecule\']/*[local-name()=\'atomArray\']/*[local-name()=\'atom\']';      // works with namespaces

  var anodes = xmlDom.evaluate(
    apath,                                    // xpath
    xmlDom,                                   // context node
    nsResolverA,                              // namespaceResolver
    XPathResult.ORDERED_NODE_ITERATOR_TYPE,   // resultType
    null);                                    // result
  // Caution Javascript language weirdness and kluge.
  // The resulting anodes is undefined, but has iterateNext.
  console.log('  atoms anodes: ', anodes);

  var atoms = [];

  var anode = anodes.iterateNext();
  var aix = 0;
  while (anode) {
    console.log('  =============== anode: ', anode);
    var aid   = anode.getAttribute('id');
    var asym = anode.getAttribute('elementType');
    var x3 = parseFloat( anode.getAttribute('x3'));
    var y3 = parseFloat( anode.getAttribute('y3'));
    var z3 = parseFloat( anode.getAttribute('z3'));
    atoms.push( {
      aix: aix,
      asym: asym,
      directCoords: [x3, y3, z3]
    });
    anode=anodes.iterateNext();
    aix++;
  }

  // Also works:
  var tstAtoms = xmlDom.documentElement.getElementsByTagName('atom');
  console.log('tstAtoms: ', tstAtoms);
  console.log('tstAtoms.length: ', tstAtoms.length);
  for (var ii = 0; ii < tstAtoms.length; ii++) {
    var tatom = tstAtoms[ii];
    console.log('  ii: ', ii,
      '  tstAtom: ', tatom,
      '  type: ', tatom.getAttribute('elementType'),
      '  coords: ', tatom.getAttribute('x3'),
      ' ', tatom.getAttribute('y3'),
      ' ', tatom.getAttribute('z3'));
  }
  console.log('\n========== end get atom info ==========\n');
  console.log('\natoms:', atoms)

  var atomMap = {};
  for (var ii = 0; ii < atoms.length; ii++) {
    atom = atoms[ii]
    atomMap[atom.aid] = atom
  }
  console.log('\nparseCml: atomMap:', atomMap)


  // Get bonds from molecule/bondArray/bond
  console.log('\n========== start get bond info ==========\n');

  var bpath = '/*[local-name()=\'molecule\']/*[local-name()=\'bondArray\']/*[local-name()=\'bond\']';      // works with namespaces

  var bnodes = xmlDom.evaluate(
    bpath,                                // xpath
    xmlDom,                  // context node
    nsResolverA,                                    // namespaceResolver
    XPathResult.ORDERED_NODE_ITERATOR_TYPE,     // resultType
    null);                                   // result
  // Caution Javascript language weirdness and kluge.
  // The resulting bnodes is undefined, but has iterateNext.

  var bnode = bnodes.iterateNext();
  bonds = []
  while (bnode) {
    console.log('  bnode: ', bnode);
    var refStg = bnode.getAttribute('atomRefs2');
    var toks = refStg.split(' ');
    console.log('    bond toks: ', toks);
    var ida = parseInt( toks[1]);
    var idb = parseInt( toks[2]);
    bonds.push( [ ida, idb] );
    bnode=bnodes.iterateNext();
  }

  console.log('\n========== end get bond info ==========\n');
  console.log('\nbonds:', bonds)

  var atomInfo = {
    description: description,
    atoms:       atoms,
    bonds:       bonds,
    elementMap:  eleMap,
    atomMap:     atomMap,
    corners:     null};

  console.log('\n========== end parseCml ==========\n');
  return atomInfo;
} // end parseCml








var readRemoteReq;
function readRemoteReq( fpath) {
  var req = new XMLHttpRequest();
  //cmlReq.onload = function() {
  //  console.log( 'cmlReq acquired');
  //};

  req.open( 'GET', fpath, false);         // async = false
  req.send( null);
  return req;
}



var readRemoteFileContent;
function readRemoteFileContent( fpath) {
  var req = readRemoteReq( fpath);
  var content = req.responseText;
  return content;
}





var readRemoteFileLines;
function readRemoteFileLines( fpath) {
  var content = readRemoteFileContent( fpath);
  var lines = content.split('\n');       // adds a final empty line
  return lines;
}




var readRemoteXmlDom;
function readRemoteXmlDom( fpath) {
  var req = readRemoteReq( fpath);
  var xmlDom = req.responseXML;
  return xmlDom;
}




var parseSmol;
function parseSmol( content) {
  console.log('\n========== start parseSmol ==========\n');

  smol = JSON.parse( content);

  var atomInfo = {
    atoms:       smol.atoms,
    basisMat:    smol.basisMat,
    bonds:       smol.bonds,
    coordType:   smol.coordType,
    description: smol.description,
    elementMap:  smol.elementMap,
    posScale:    smol.posScale};

  console.log('\n========== end parseSmol ==========\n');
  console.log('atomInfo:\n', atomInfo);
  return atomInfo;
} // end parseSmol



var directToCartesian;
function directToCartesian( posScale, basisMatTranspose, coordVec) {
  console.log('directToCartesian: coordVec: %s', formatVector3( coordVec));
  var eps = 1.e-2;
  if (coordVec.x < -eps || coordVec.x > 1 + eps)
    throwerr('invalid coordVec: ' + coordVec);
  if (coordVec.y < -eps || coordVec.y > 1 + eps)
    throwerr('invalid coordVec: ' + coordVec);
  if (coordVec.z < -eps || coordVec.z > 1 + eps)
    throwerr('invalid coordVec: ' + coordVec);
  cartCoordVec = coordVec.clone();
  cartCoordVec.applyMatrix3( basisMatTranspose);
  cartCoordVec.multiplyScalar( posScale);
  return cartCoordVec;
}



var cartesianToProjection;
function cartesianToProjection( aoffset, minCartVec, rangeCartVec, coordVec) {
  projCoordVec = coordVec.clone();
  projCoordVec.sub( minCartVec);
  projCoordVec.divide( rangeCartVec);
  // Move the center of the unit cube to the origin
  projCoordVec.x -= aoffset;
  projCoordVec.y -= aoffset;
  projCoordVec.z -= aoffset;
  return projCoordVec;
}












var getCorners;
function getCorners( aoffset, coordType, posScale, basisMat) {
  console.log('===== getCorners: start');

  var basisMatTranspose = basisMat.clone();
  basisMatTranspose.transpose();

  var corners = null;
  if (coordType === 'direct') {
    // Make the 8 corners
    corners = [ null, null];
    for (var ii = 0; ii < 2; ii++) {
      corners[ii] = [ null, null];
      for (var jj = 0; jj < 2; jj++) {
        corners[ii][jj] = [ null, null];
        for (var kk = 0; kk < 2; kk++) {
          corners[ii][jj][kk] = new THREE.Vector3( ii, jj, kk);
        }
      }
    }

  } // if 'direct'

  else if (coordType === 'cartesian') {
    corners = null;
  }

  else throwerr('invalid coordType: ' + coordType)
  console.log('===== getCorners: end.  corners: %o', corners);
  return corners;
} // end getCorners






// Get atomMap
// Return map atom.aix -> atom
var getAtomMap;
function getAtomMap( atoms) {
  console.log('===== getAtomMap: start');
  var atomMap = {};
  for (var ii = 0; ii < smol.atoms.length; ii++) {
    atom = atoms[ii]
    atomMap[atom.aix] = atom
  }
  console.log('===== getAtomMap: end.  atomMap: %o', atomMap);
  return atomMap;
}




var printArray;
function printArray( msg, arr) {
  console.log('\n========== ', msg, ' ==========');
  for (var ii = 0; ii < arr.length; ii++) {
    console.log('  [' + ii + ']: ' + String( arr[ii]));
  }
}





// Read the TEXT elements that are directly under the specified DOM id.
// Return a single string.

var getDocTextContent;
function getDocTextContent ( id ) {
   var docEle = document.getElementById ( id );
   var content = '';
   var nd = docEle.firstChild;
   while (nd) {
     if (nd.nodeType === 3) content += nd.textContent;
     nd = nd.nextSibling;
   }
   return content;
}



// Read the TEXT elements that are directly under the specified DOM id.
// Return an array of lines.

var getDocTextLines;
function getDocTextLines ( id ) {
  var str = getDocTextContent( id);
  var lines = str.trim().split('\n');
  return lines;
}


var throwerr;
function throwerr( msg) {
  throw msg;
}


var formatAtom;
function formatAtom( atom) {
  var res = '';
  res += '    aix: ' + atom.aix + '\n';
  res += '    asym: ' + atom.asym + '\n';
  res += '    directCoords: ' + atom.directCoords + '\n';
  if (atom.cartCoordVec)
    res += '    cartCoordVec: ' + formatVector3( atom.cartCoordVec) + '\n';
  if (atom.projCoordVec)
    res += '    projCoordVec: ' + formatVector3( atom.projCoordVec) + '\n';
  return res;
}



var formatMatrix3;
function formatMatrix3( mat) {
  var eles = mat.elements;
  var res = '';
  res += '  ' + eles[0] + '  ' + eles[3] + '  ' + eles[6] + '\n';
  res += '  ' + eles[1] + '  ' + eles[4] + '  ' + eles[7] + '\n';
  res += '  ' + eles[2] + '  ' + eles[5] + '  ' + eles[8] + '\n';
  return res;
}



var formatVector3;
function formatVector3( vec) {
  var res = '  ';
  if (typeof vec.x === 'number') res += vec.x.toFixed(5);
  else res += String( vec.x);
  res += '  ';

  if (typeof vec.y === 'number') res += vec.y.toFixed(5);
  else res += String( vec.y);
  res += '  ';

  if (typeof vec.z === 'number') res += vec.z.toFixed(5);
  else res += String( vec.z);
  return res;
}






// MAIN

// standard global variables
var container, scene, camera, renderer, controls, stats;
//var keyboard = new THREEx.KeyboardState();
var clock = new THREE.Clock();
// custom global variables
var cube;


init();

animate();





