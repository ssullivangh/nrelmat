<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
  <title>NREL MatDB</title>
  <meta http-equiv="Content-Type" content="text/html;charset=UTF-8"/>
  <meta name="keywords" content="python web application" />
  <meta name="description" content="NREL MatDB" />
  <link rel="shortcut icon" href="${request.static_url('testmako:static/images/favicon.ico')}" />

<style>



  div#topnav table {  border-spacing: 5; }

  div#topnav a:link {
    text-decoration: none; }

  td.navButtonStd {
    color: #ff0000;
    background-color: #0060b0;
    padding: 3px 8px 3px 8px; }

  td.navButtonInv {
    color: #ff0000;
    background-color: #ffffff;
    padding: 3px 8px 3px 8px; }

  div.navButtonStd {
    color: #ffffff;
    background-color: #0060b0;
    font-style: normal;
    font-variant: small-caps;
  }
  div.navButtonInv {
    color: #0060b0;
    background-color: #ffffff;
    font-style: normal;
    font-variant: small-caps;
  }


  table.subbanner {
    width: 1000px;
    border-spacing: 1;
    border-collapse: separate;
    margin-bottom: 10px;
  }

  td.subbanner {
    color: #0060b0;
    background-color: #e0e0e0;
    padding: 5px 5px 5px 5px;
  }

  th.rightAlign { text-align: right; }

  th.varMapLeft {
    background-color: #c0c0c0;
  font-size: 100%;
    text-align: left;
  }

  th.varMapRight {
    background-color: #c0c0c0;
  font-size: 100%;
    text-align: right;
  }

  td.varMapLeft {
    background-color: #c0c0c0;
  font-size: 100%;
    text-align: left;
  }

  td.varMapRight {
    background-color: #c0c0c0;
  font-size: 100%;
    text-align: right;
  }

  /* Used for error messages */
  div.cerrMessage {
    color: red;
    font-size: large;
    font-weight: bold;
  }

  span.example {
    font-family: Arial, Helvetica;
    font-style: bold;
    font-size: 150%;
    color: #006000;
  }

  /* Used in query results for the current page number */
  input.here {
    color: #000000;
    background-color: #ffff00;
  }
  /* Used in query results for other page numbers */
  input.there {
    color: #0000ee;
    background-color: #ffffff;
  }

  div.varMap {
    color: #000000;
	background-color: #c0c0e0;
  }
</style>

<%block name="blkHead">
<!-- tmBase.blkHead: (overridden by caller) -->
<script language="javascript" type="text/javascript">
function setInitialFocus() {
}
</script>
</%block>

</head>


<body onload="setInitialFocus();">

  <div id="wrapper">

    <div id="nrelheader">
      <img src="static/images/banner_nrel.png" alt="NREL - National Renewable Energy Laboratory"
      usemap="#nrelheader_map" height="86" width="1000"/>
      <map name="nrelheader_map" id="nrelheader_map">
        <area shape="rect" coords="0,0,299,86" href="http://www.nrel.gov" alt="NREL - National Renewable Energy Laboratory" />
        <area shape="rect" coords="300,0,1000,86" href="http://hpc.nrel.gov" alt="NREL High Performance Computing Center" />
      </map>
    </div>

    <div id="topnav">
      <table>
        <tr>
          ## navList has tuples: [tag, url, cssClass=navButtonStd/Inv]
          % for tuple in navList:
          <td class="${tuple[2]}">
            <a href="${tuple[1]}">
              <div class="${tuple[2]}"> ${tuple[0]} </div>
            </a>
          </td>
          % endfor
        </tr>
      </table>
    </div>

    <div id="subheader">
      ##<img src="static/images/banner_sub_a.jpg" alt=""
      ##   height="40" width="1000"/>
      <table class="subbanner">
      <tr> <td class="subbanner">${subHead}</td></tr>
      </table>
    </div>

    <div id="maincontent">
    % if len(errMsg) > 0:
    <!-- tmBase: errMsg: -->
    <p/>
    <div class="cerrMessage"> ${errMsg} </div>
    <p/>
    % endif
    ## Include all body from the caller
    <!-- tmBase: start included body -->
    ${self.body()}
    <!-- tmBase: end included body -->
    </div>
  </div>

</body>
</html>

