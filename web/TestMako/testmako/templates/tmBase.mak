<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
  <title>NREL MatDB</title>
  <meta http-equiv="Content-Type" content="text/html;charset=UTF-8"/>
  <meta name="keywords" content="python web application" />
  <meta name="description" content="NREL MatDB" />
  <link rel="shortcut icon" href="${request.static_url('testmako:static/images/favicon.ico')}" />

<style>

  h2.title { color: #0067b8; }

  table.subNav  { border: 1px solid white; border-collapse: collapse;}

  th.subNav, td.subNav  {
    border: 2px solid yellow; padding: 2px 5px 2px 5px;
    /* padding: top right bottom left */
  }

  th.rightAlign { text-align: right; }

  td.mainNav  {
    padding: 2px 2px 2px 2px;
    border-width: 2px;
    border-style: solid;
    border-top-color    : white;
    border-right-color  : gray;
    border-bottom-color : white;
    border-left-color   : white;
    padding: 5px 5px 5px 5px;   /* padding: top right bottom left */
  }

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

  /* Used for navigation buttons */
  div.navButton {
    color: #0000ee;
    font-style: italic;
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

<!-- Two rows: navigation and body -->
<table class="mainNav" style="width:100%;">

<!-- First row: navigation -->
<tr>
<td class="mainNav" style="vertical-align:top;">
  <div>
  <table class="subNav" >
  <tr>
  % for pair in navList:
    <th class="subNav">
      <a href="${pair[1]}"> <div class="navButton"> ${pair[0]} </div></a>
    </th>
  % endfor
  </tr>
  </table>
  </div>
</td>
</tr>


<!-- Second row: body -->
<tr>
<td>
  <h2 class="title"> NREL MatDB: <%block name="blkTitle"/>
  </h2>

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
</td>
</tr>
</table>

</body>
</html>

