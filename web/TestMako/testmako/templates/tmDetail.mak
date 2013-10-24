<%inherit file="tmBase.mak"/>


##<%block name="blkHead">
##<!-- tmDetail.blkHead: overrides tmBase.mak: blkHead -->
##</%block>


<!-- tmDetail.body: start -->

% if len(errMsg) == 0:
  <div id="body">
  <a href="visualize?midentspec=${midentval}"> Visualize </a>

  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  Download statistics as:
    <a href="downloadSql?format=python&midentspec=${midentval}"> Python </a>
	&nbsp;&nbsp; or &nbsp;&nbsp;
    <a href="downloadSql?format=json&midentspec=${midentval}"> JSON </a>

  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  Download original files as:
    <a href="downloadFlat?format=tar.gz&midentspec=${midentval}"> tar.gz </a>

  <p>
  <table style="border:2px solid #00ff00;
    border-collapse: collapse;
    margin-left: auto;
    margin-right: auto;">

    % for pair in db_pairs:
      <tr>
      <td style="border:2px solid #c0c0c0;"> ${pair[0]} </td>
      <td style="border:2px solid #c0c0c0;"> ${pair[1]} </td>
      </tr>
    % endfor
  </table>
  </div>
% endif

<!-- tmDetail.body: end -->
